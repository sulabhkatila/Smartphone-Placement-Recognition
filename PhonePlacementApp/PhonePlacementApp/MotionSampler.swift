import CoreMotion
import Foundation

struct MotionSample: Codable, Sendable {
    let x: Double
    let y: Double
    let z: Double
    let timestamp: Double
}

struct MotionPayload: Codable, Sendable {
    let accelerometer: [MotionSample]
    let gyroscope: [MotionSample]
}

final class MotionSampler: @unchecked Sendable {
    private let motionManager = CMMotionManager()
    private let queue = OperationQueue()
    private let lock = NSLock()

    private var accelerometerSamples: [MotionSample] = []
    private var gyroscopeSamples: [MotionSample] = []

    var isAvailable: Bool {
        motionManager.isAccelerometerAvailable && motionManager.isGyroAvailable
    }

    func start() {
        guard isAvailable else { return }

        let interval = 1.0 / 100.0
        motionManager.accelerometerUpdateInterval = interval
        motionManager.gyroUpdateInterval = interval

        motionManager.startAccelerometerUpdates(to: queue) { [weak self] data, _ in
            guard let self, let data else { return }
            let sample = MotionSample(
                x: data.acceleration.x,
                y: data.acceleration.y,
                z: data.acceleration.z,
                timestamp: data.timestamp
            )
            self.lock.lock()
            self.accelerometerSamples.append(sample)
            self.lock.unlock()
        }

        motionManager.startGyroUpdates(to: queue) { [weak self] data, _ in
            guard let self, let data else { return }
            let sample = MotionSample(
                x: data.rotationRate.x,
                y: data.rotationRate.y,
                z: data.rotationRate.z,
                timestamp: data.timestamp
            )
            self.lock.lock()
            self.gyroscopeSamples.append(sample)
            self.lock.unlock()
        }
    }

    func stop() {
        motionManager.stopAccelerometerUpdates()
        motionManager.stopGyroUpdates()
    }

    func drainPayload() -> MotionPayload {
        lock.lock()
        let accel = accelerometerSamples
        let gyro = gyroscopeSamples
        accelerometerSamples = []
        gyroscopeSamples = []
        lock.unlock()
        return MotionPayload(accelerometer: accel, gyroscope: gyro)
    }
}
