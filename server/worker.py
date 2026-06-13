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


import sys
import json
import logging

# Configure logging to write to stderr so it doesn't corrupt stdout JSON
logging.basicConfig(level=logging.INFO, stream=sys.stderr, format='[Python Worker] %(message)s')

def main():
    logging.info("Starting up, loading model...")
    try:
        model = get_model()
        logging.info("Model loaded successfully. Ready for jobs.")
    except Exception as e:
        logging.error(f"FATAL: Failed to load model: {e}")
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            job = json.loads(line)
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse JSON: {e}")
            continue

        job_id = job.get("job_id")
        client_id = job.get("client_id")
        raw_data = job.get("raw_data")

        result = {
            "job_id": job_id,
            "client_id": client_id,
            "prediction": None,
            "error": None,
        }

        try:
            # 1. Feature extraction and preprocessing
            x = _ios_dataformat(raw_data, model.selected_features)
            
            # 2. Run ensemble prediction
            prediction = model.run_predictions(x)
            result["prediction"] = prediction
        except ValueError as ve:
            result["error"] = str(ve)
        except Exception as e:
            logging.error(f"Error processing job {job_id}: {e}")
            traceback.print_exc(file=sys.stderr)
            result["error"] = str(e)

        # Output the result as JSON to stdout
        try:
            print(json.dumps(result))
            sys.stdout.flush()
        except Exception as e:
            logging.error(f"Failed to write result to stdout: {e}")

if __name__ == "__main__":
    main()
