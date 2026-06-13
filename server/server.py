import json
import uuid
import asyncio
import multiprocessing
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from worker import start_worker_pool, stop_worker_pool


# ---------------------------------------------------------------------------
# Global State
# ---------------------------------------------------------------------------

job_queue: multiprocessing.Queue = None
result_queue: multiprocessing.Queue = None
worker_processes: list = []

class SensorClient:
    def __init__(self, ws: WebSocket):
        self.ws = ws

sensor_clients = {}
dashboard_clients = set()


# ---------------------------------------------------------------------------
# Result Collector
# ---------------------------------------------------------------------------

def _blocking_get_result():
    try:
        return result_queue.get(timeout=0.1)
    except Exception:
        return None


async def result_collector_loop():
    """
    Async loop that polls the result_queue for completed inference jobs
    and dispatches results back to the correct phone client + dashboard.
    """
    loop = asyncio.get_event_loop()
    
    while True:
        try:
            # Poll the multiprocessing result queue from the async loop
            result = await loop.run_in_executor(None, _blocking_get_result)
            
            if result is None:
                await asyncio.sleep(0.05)
                continue
            
            client_id = result.get("client_id")
            prediction = result.get("prediction")
            error = result.get("error")
            
            client = sensor_clients.get(client_id)
            if client:
                if error:
                    try:
                        await client.ws.send_json({"error": error})
                    except Exception:
                        pass
                elif prediction:
                    try:
                        await client.ws.send_json(prediction)
                    except Exception:
                        pass
                    await _broadcast_to_dashboards(prediction)
                    
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[Collector] Unexpected error: {e}")
            await asyncio.sleep(0.1)


# ---------------------------------------------------------------------------
# FastAPI App & Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    global job_queue, result_queue, worker_processes
    
    num_workers = 4
    print(f"[Server] Starting {num_workers} worker processes...")
    job_queue = multiprocessing.Queue(maxsize=100)
    result_queue = multiprocessing.Queue(maxsize=100)
    
    worker_processes = start_worker_pool(num_workers, job_queue, result_queue)
    collector_task = asyncio.create_task(result_collector_loop())
    
    yield
    
    print("[Server] Shutting down...")
    collector_task.cancel()
    stop_worker_pool(worker_processes, job_queue)
    print("[Server] Shutdown complete.")


app = FastAPI(lifespan=lifespan)

# Mount static directory for the dashboard
app.mount("/dashboard", StaticFiles(directory="static", html=True), name="static")


@app.get("/")
async def health():
    return {"status": "ok", "websocket_endpoint": "/predict"}


@app.websocket("/predict")
async def predict(websocket: WebSocket):
    await websocket.accept()
    
    client_id = str(uuid.uuid4())
    sensor_clients[client_id] = SensorClient(websocket)
    job_counter = 0
    buffer = []
    
    try:
        while True:
            data = await websocket.receive_text()
            try:
                raw_data = json.loads(data)
                buffer.append(raw_data)
                
                # Keep only the last 10 seconds of data
                if len(buffer) > 10:
                    buffer.pop(0)
                
                if len(buffer) == 10:
                    # Once we have 10 seconds, combine and send as a job
                    combined_data = _combine_10_seconds_data(buffer)
                    job_id = f"{client_id}-{job_counter}"
                    job_counter += 1
                    
                    try:
                        job_queue.put_nowait({
                            "job_id": job_id,
                            "client_id": client_id,
                            "raw_data": combined_data,
                        })
                    except multiprocessing.queues.Full:
                        await websocket.send_json({"error": "Server is overloaded, dropping frame."})
                else:
                    # Not enough data yet, send a loading state
                    loading_state = {"status": "loading", "buffered_seconds": len(buffer)}
                    await websocket.send_json(loading_state)
                    await _broadcast_to_dashboards(loading_state)
                    
            except ValueError as ve:
                await websocket.send_json({"error": str(ve)})
            except Exception as e:
                await websocket.send_json({"error": f"Internal error: {str(e)}"})
    except WebSocketDisconnect:
        pass
    finally:
        sensor_clients.pop(client_id, None)


@app.websocket("/ws/dashboard")
async def dashboard_websocket(websocket: WebSocket):
    await websocket.accept()
    dashboard_clients.add(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        dashboard_clients.remove(websocket)


async def _broadcast_to_dashboards(message: dict):
    if not dashboard_clients:
        return
    disconnected = set()
    for client in dashboard_clients:
        try:
            await client.send_json(message)
        except Exception:
            disconnected.add(client)
    for client in disconnected:
        dashboard_clients.remove(client)


def _combine_10_seconds_data(buffer: list) -> dict:
    """
    Combines a list of 1-second raw_data dicts into a single dict
    that represents 10 seconds of continuous data.
    """
    combined = {}
    if not buffer:
        return combined
        
    if "motion" in buffer[0]:
        combined["motion"] = []
        for b in buffer:
            combined["motion"].extend(b.get("motion", []))
    elif "accelerometer" in buffer[0] and "gyroscope" in buffer[0]:
        combined["accelerometer"] = []
        combined["gyroscope"] = []
        for b in buffer:
            combined["accelerometer"].extend(b.get("accelerometer", []))
            combined["gyroscope"].extend(b.get("gyroscope", []))
    return combined


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
