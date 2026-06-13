package main

import (
	"bufio"
	"encoding/json"
	"log"
	"os"
	"os/exec"
)

type Job struct {
	JobID    string                 `json:"job_id"`
	ClientID string                 `json:"client_id"`
	RawData  map[string]interface{} `json:"raw_data"`
}

type PredictionResult struct {
	JobID      string             `json:"job_id"`
	ClientID   string             `json:"client_id"`
	Prediction map[string]float64 `json:"prediction"`
	Error      *string            `json:"error"`
}

type WorkerPool struct {
	NumWorkers  int
	JobQueue    chan Job
	ResultQueue chan PredictionResult
	cmds        []*exec.Cmd
}

func NewWorkerPool(numWorkers int) *WorkerPool {
	return &WorkerPool{
		NumWorkers:  numWorkers,
		JobQueue:    make(chan Job, 100),
		ResultQueue: make(chan PredictionResult, 100),
	}
}

func (wp *WorkerPool) Start() {
	for i := 0; i < wp.NumWorkers; i++ {
		go wp.runWorker(i)
	}
}

func (wp *WorkerPool) runWorker(id int) {
	pythonPath := "./venv/bin/python"
	if _, err := os.Stat(pythonPath); os.IsNotExist(err) {
		pythonPath = "python3" // fallback
	}

	cmd := exec.Command(pythonPath, "worker.py")

	stdin, err := cmd.StdinPipe()
	if err != nil {
		log.Fatalf("Worker %d stdin pipe error: %v", id, err)
	}

	stdout, err := cmd.StdoutPipe()
	if err != nil {
		log.Fatalf("Worker %d stdout pipe error: %v", id, err)
	}

	// Python logs to stderr, pass it straight to our console
	cmd.Stderr = os.Stderr

	if err := cmd.Start(); err != nil {
		log.Fatalf("Worker %d failed to start: %v", id, err)
	}
	wp.cmds = append(wp.cmds, cmd)

	log.Printf("[Pool] Worker %d started (PID: %d)", id, cmd.Process.Pid)

	// Routine to read stdout asynchronously
	go func() {
		scanner := bufio.NewScanner(stdout)
		// Increase buffer capacity if JSON lines get large (1MB)
		buf := make([]byte, 0, 64*1024)
		scanner.Buffer(buf, 1024*1024)

		for scanner.Scan() {
			line := scanner.Text()
			var res PredictionResult
			if err := json.Unmarshal([]byte(line), &res); err != nil {
				log.Printf("Worker %d invalid JSON from stdout: %s", id, line)
				continue
			}
			wp.ResultQueue <- res
		}
		if err := scanner.Err(); err != nil {
			log.Printf("Worker %d stdout read error: %v", id, err)
		}
	}()

	encoder := json.NewEncoder(stdin)
	for job := range wp.JobQueue {
		if err := encoder.Encode(job); err != nil {
			log.Printf("Worker %d failed to write job: %v", id, err)
		}
	}

	stdin.Close()
	cmd.Wait()
	log.Printf("[Pool] Worker %d stopped", id)
}

func (wp *WorkerPool) Stop() {
	log.Println("[Pool] Shutting down workers...")
	close(wp.JobQueue)
	for _, cmd := range wp.cmds {
		if cmd.Process != nil {
			cmd.Process.Kill()
		}
	}
}
