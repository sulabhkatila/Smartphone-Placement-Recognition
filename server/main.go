package main

import (
	"encoding/json"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
)

var (
	workerPool *WorkerPool
	hub        *Hub
)

func main() {
	log.Println("Starting Go backend...")

	// Initialize the Hybrid Python Worker Pool
	workerPool = NewWorkerPool(4)
	workerPool.Start()

	// Initialize the WebSocket Hub for dashboards
	hub = NewHub()
	go hub.Run()

	// Start result collector loop
	go func() {
		for result := range workerPool.ResultQueue {
			// Find the client and send the prediction back
			if client, ok := hub.GetSensorClient(result.ClientID); ok {
				msg, err := json.Marshal(result)
				if err == nil {
					client.Send <- msg
				}
			}

			// Broadcast to all dashboards
			if result.Error == nil {
				msg, err := json.Marshal(result)
				if err == nil {
					hub.Broadcast <- msg
				}
			}
		}
	}()

	// Setup HTTP routes
	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{
			"status":             "ok",
			"websocket_endpoint": "/predict",
		})
	})

	http.Handle("/dashboard/", http.StripPrefix("/dashboard/", http.FileServer(http.Dir("static"))))
	http.HandleFunc("/dashboard", func(w http.ResponseWriter, r *http.Request) {
		http.Redirect(w, r, "/dashboard/", http.StatusMovedPermanently)
	})

	http.HandleFunc("/predict", handleSensorWebSocket)
	http.HandleFunc("/ws/dashboard", handleDashboardWebSocket)

	// Start server in background
	server := &http.Server{Addr: ":8000"}
	go func() {
		log.Println("HTTP Server listening on :8000")
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("ListenAndServe error: %v", err)
		}
	}()

	// Graceful shutdown
	stop := make(chan os.Signal, 1)
	signal.Notify(stop, os.Interrupt, syscall.SIGTERM)
	<-stop

	log.Println("Shutting down server...")
	workerPool.Stop()
	server.Close()
	log.Println("Shutdown complete.")
}
