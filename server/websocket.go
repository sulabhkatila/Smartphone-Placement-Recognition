package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"sync"
	"github.com/google/uuid"
	"github.com/gorilla/websocket"
)

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool {
		return true // Allow all for now
	},
}

// Hub maintains the set of active clients and broadcasts messages to dashboards.
type Hub struct {
	Dashboards    map[*websocket.Conn]bool
	SensorClients map[string]*SensorClient
	Broadcast     chan []byte
	Register      chan *websocket.Conn
	Unregister    chan *websocket.Conn
	mu            sync.RWMutex
}

func NewHub() *Hub {
	return &Hub{
		Dashboards:    make(map[*websocket.Conn]bool),
		SensorClients: make(map[string]*SensorClient),
		Broadcast:     make(chan []byte),
		Register:      make(chan *websocket.Conn),
		Unregister:    make(chan *websocket.Conn),
	}
}

func (h *Hub) Run() {
	for {
		select {
		case client := <-h.Register:
			h.mu.Lock()
			h.Dashboards[client] = true
			h.mu.Unlock()
		case client := <-h.Unregister:
			h.mu.Lock()
			if _, ok := h.Dashboards[client]; ok {
				delete(h.Dashboards, client)
				client.Close()
			}
			h.mu.Unlock()
		case message := <-h.Broadcast:
			h.mu.RLock()
			for client := range h.Dashboards {
				err := client.WriteMessage(websocket.TextMessage, message)
				if err != nil {
					client.Close()
					// Not deleting from map here to avoid concurrent modification,
					// it will fail again or we can let Unregister handle it if we redesign.
					// For simplicity in a tight loop:
				}
			}
			h.mu.RUnlock()
		}
	}
}

func (h *Hub) AddSensorClient(id string, client *SensorClient) {
	h.mu.Lock()
	defer h.mu.Unlock()
	h.SensorClients[id] = client
}

func (h *Hub) RemoveSensorClient(id string) {
	h.mu.Lock()
	defer h.mu.Unlock()
	delete(h.SensorClients, id)
}

func (h *Hub) GetSensorClient(id string) (*SensorClient, bool) {
	h.mu.RLock()
	defer h.mu.RUnlock()
	client, ok := h.SensorClients[id]
	return client, ok
}

type SensorClient struct {
	ID   string
	Conn *websocket.Conn
	Send chan []byte
}

func handleDashboardWebSocket(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Println(err)
		return
	}
	hub.Register <- conn

	// Keep alive
	go func() {
		defer func() {
			hub.Unregister <- conn
		}()
		for {
			_, _, err := conn.ReadMessage()
			if err != nil {
				break
			}
		}
	}()
}

func handleSensorWebSocket(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Println(err)
		return
	}

	clientID := uuid.New().String()
	client := &SensorClient{
		ID:   clientID,
		Conn: conn,
		Send: make(chan []byte, 100),
	}

	hub.AddSensorClient(clientID, client)

	// Writer goroutine for sensor client
	go func() {
		defer conn.Close()
		for msg := range client.Send {
			if err := conn.WriteMessage(websocket.TextMessage, msg); err != nil {
				return
			}
		}
	}()

	// Reader goroutine for sensor client
	go func() {
		defer func() {
			hub.RemoveSensorClient(clientID)
			close(client.Send)
			conn.Close()
		}()

		var buffer []map[string]interface{}
		jobCounter := 0

		for {
			_, msg, err := conn.ReadMessage()
			if err != nil {
				break
			}

			var rawData map[string]interface{}
			if err := json.Unmarshal(msg, &rawData); err != nil {
				sendError(client, fmt.Sprintf("Invalid JSON: %v", err))
				continue
			}

			buffer = append(buffer, rawData)
			if len(buffer) > 10 {
				buffer = buffer[1:]
			}

			if len(buffer) == 10 {
				combined := combine10SecondsData(buffer)
				jobID := fmt.Sprintf("%s-%d", clientID, jobCounter)
				jobCounter++

				job := Job{
					JobID:    jobID,
					ClientID: clientID,
					RawData:  combined,
				}

				select {
				case workerPool.JobQueue <- job:
					// Enqueued successfully
				default:
					sendError(client, "Server is overloaded, dropping frame.")
				}
			} else {
				// Not enough data yet, send loading state
				loading := map[string]interface{}{
					"status":           "loading",
					"buffered_seconds": len(buffer),
				}
				sendJSON(client, loading)
				
				// Optional: broadcast loading state to dashboard too
				b, _ := json.Marshal(loading)
				hub.Broadcast <- b
			}
		}
	}()
}

func sendError(client *SensorClient, errMsg string) {
	msg := map[string]string{"error": errMsg}
	sendJSON(client, msg)
}

func sendJSON(client *SensorClient, data interface{}) {
	b, err := json.Marshal(data)
	if err == nil {
		client.Send <- b
	}
}

func combine10SecondsData(buffer []map[string]interface{}) map[string]interface{} {
	combined := make(map[string]interface{})
	if len(buffer) == 0 {
		return combined
	}

	if _, ok := buffer[0]["motion"]; ok {
		var motion []interface{}
		for _, b := range buffer {
			if m, ok := b["motion"].([]interface{}); ok {
				motion = append(motion, m...)
			}
		}
		combined["motion"] = motion
	} else if _, ok := buffer[0]["accelerometer"]; ok {
		var acc, gyr []interface{}
		for _, b := range buffer {
			if a, ok := b["accelerometer"].([]interface{}); ok {
				acc = append(acc, a...)
			}
			if g, ok := b["gyroscope"].([]interface{}); ok {
				gyr = append(gyr, g...)
			}
		}
		combined["accelerometer"] = acc
		combined["gyroscope"] = gyr
	}
	return combined
}
