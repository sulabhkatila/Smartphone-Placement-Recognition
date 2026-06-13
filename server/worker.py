import multiprocessing
import traceback
import numpy as np

from model import get_model
from feature_utils import extract_all_features


def _ios_dataformat(raw_data: dict, selected_features: list) -> np.ndarray:
    """
    Parses accelerometer and gyroscope measurements provided in default iOS CoreMotion formats,
    processes them (converting G's to m/s^2, computing L2 norm magnitudes, resampling to 100 Hz),
    extracts the required signal processing features, and formats them for the model.
    """
    # 1. Parse different iOS CoreMotion structures
    if "motion" in raw_data:
        motion_list = raw_data["motion"]
        t_acc = np.array([m.get("timestamp") or m.get("time") for m in motion_list])
        t_gyr = t_acc

        acc_x = np.array(
            [
                (m.get("acceleration") or m.get("userAcceleration"))["x"]
                for m in motion_list
            ]
        )
        acc_y = np.array(
            [
                (m.get("acceleration") or m.get("userAcceleration"))["y"]
                for m in motion_list
            ]
        )
        acc_z = np.array(
            [
                (m.get("acceleration") or m.get("userAcceleration"))["z"]
                for m in motion_list
            ]
        )

        gyr_x = np.array([m.get("rotationRate")["x"] for m in motion_list])
        gyr_y = np.array([m.get("rotationRate")["y"] for m in motion_list])
        gyr_z = np.array([m.get("rotationRate")["z"] for m in motion_list])

    elif "accelerometer" in raw_data and "gyroscope" in raw_data:
        acc_list = raw_data["accelerometer"]
        gyr_list = raw_data["gyroscope"]

        t_acc = np.array([a.get("timestamp") or a.get("time") for a in acc_list])
        t_gyr = np.array([g.get("timestamp") or g.get("time") for g in gyr_list])

        acc_x = np.array([a["x"] for a in acc_list])
        acc_y = np.array([a["y"] for a in acc_list])
        acc_z = np.array([a["z"] for a in acc_list])

        gyr_x = np.array([g["x"] for g in gyr_list])
        gyr_y = np.array([g["y"] for g in gyr_list])
        gyr_z = np.array([g["z"] for g in gyr_list])
    else:
        raise ValueError(
            "Invalid iOS data format. Payload must contain 'motion' array or separate 'accelerometer' and 'gyroscope' arrays."
        )

    if len(t_acc) < 5 or len(t_gyr) < 5:
        raise ValueError(
            "Insufficient data points in iOS CoreMotion arrays to perform analysis."
        )

    # Convert G's to m/s^2 for accelerometer measurements (iOS CoreMotion uses G's by default, model expects m/s^2)
    acc_x = acc_x * 9.80665
    acc_y = acc_y * 9.80665
    acc_z = acc_z * 9.80665

    # Compute L2 Norm (orientation-invariant magnitude)
    acc_norm = np.sqrt(acc_x**2 + acc_y**2 + acc_z**2)
    gyr_norm = np.sqrt(gyr_x**2 + gyr_y**2 + gyr_z**2)

    # Normalize timestamps relative to the start of the window
    t0 = min(t_acc[0], t_gyr[0])
    t_acc_rel = t_acc - t0
    t_gyr_rel = t_gyr - t0

    # Verify the window duration (should span roughly 10 seconds)
    duration = max(t_acc_rel[-1], t_gyr_rel[-1])
    if duration < 9.0:
        raise ValueError(
            f"Input data duration is too short. Got {duration:.2f} seconds, expected at least 9.0s to construct a 10s walking window."
        )

    # Resample signals to exactly 100 Hz over a 10-second window (1000 samples)
    t_target = np.linspace(0, 10, 1000)
    acc_resampled = np.interp(t_target, t_acc_rel, acc_norm)
    gyr_resampled = np.interp(t_target, t_gyr_rel, gyr_norm)

    # Extract the full suite of signal processing features
    features = extract_all_features(acc_resampled, gyr_resampled)

    # Map and order the features to match the exact 50 expected features
    x = []
    for f in selected_features:
        if f in features:
            x.append(features[f])
        else:
            # Fallback default value (should not happen since we compute everything)
            x.append(0.0)

    return np.array(x, dtype=float)


def worker_process(
    worker_id: int,
    job_queue: multiprocessing.Queue,
    result_queue: multiprocessing.Queue,
):
    """
    Main loop for a worker process.
    
    Each worker:
    1. Loads the model independently (own memory space).
    2. Waits for jobs on job_queue.
    3. Runs feature extraction + inference.
    4. Puts results on result_queue.
    """
    print(f"[Worker {worker_id}] Starting up, loading model...")
    
    try:
        model = get_model()
        print(f"[Worker {worker_id}] Model loaded successfully. Ready for jobs.")
    except Exception as e:
        print(f"[Worker {worker_id}] FATAL: Failed to load model: {e}")
        traceback.print_exc()
        return
    
    jobs_processed = 0
    
    while True:
        try:
            job = job_queue.get()
            
            # Sentinel: None means shut down
            if job is None:
                print(f"[Worker {worker_id}] Received shutdown signal. Processed {jobs_processed} jobs.")
                break
            
            job_id = job["job_id"]
            client_id = job["client_id"]
            raw_data = job["raw_data"]
            
            try:
                # 1. Feature extraction and preprocessing
                x = _ios_dataformat(raw_data, model.selected_features)
                
                # 2. Run ensemble prediction
                prediction = model.run_predictions(x)
                error = None
            except ValueError as ve:
                prediction = None
                error = str(ve)
            
            result = {
                "job_id": job_id,
                "client_id": client_id,
                "worker_id": worker_id,
                "prediction": prediction,
                "error": error,
            }
            
            result_queue.put(result)
            jobs_processed += 1
            
        except Exception as e:
            error_msg = f"[Worker {worker_id}] Error processing job: {e}"
            print(error_msg)
            traceback.print_exc()
            
            # Still send a result so the server doesn't hang waiting
            try:
                result_queue.put({
                    "job_id": job.get("job_id", "unknown"),
                    "client_id": job.get("client_id", "unknown"),
                    "worker_id": worker_id,
                    "prediction": None,
                    "error": str(e),
                })
            except Exception:
                pass


def start_worker_pool(
    num_workers: int,
    job_queue: multiprocessing.Queue,
    result_queue: multiprocessing.Queue,
) -> list:
    """
    Spawn num_workers worker processes.
    
    Returns:
        list[multiprocessing.Process]: The list of running worker processes.
    """
    workers = []
    for i in range(num_workers):
        p = multiprocessing.Process(
            target=worker_process,
            args=(i, job_queue, result_queue),
            name=f"InferenceWorker-{i}",
            daemon=True,
        )
        p.start()
        workers.append(p)
        print(f"[Pool] Spawned worker process {i} (PID: {p.pid})")
    
    return workers


def stop_worker_pool(
    workers: list,
    job_queue: multiprocessing.Queue,
    timeout: float = 10.0,
):
    """
    Gracefully shut down all workers by sending sentinel values and joining.
    """
    print(f"[Pool] Sending shutdown signals to {len(workers)} workers...")
    for _ in workers:
        job_queue.put(None)
    
    for w in workers:
        w.join(timeout=timeout)
        if w.is_alive():
            print(f"[Pool] Worker {w.name} didn't stop gracefully, terminating...")
            w.terminate()
    
    print("[Pool] All workers stopped.")
