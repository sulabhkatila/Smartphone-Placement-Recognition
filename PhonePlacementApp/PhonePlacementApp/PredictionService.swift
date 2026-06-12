import Foundation

enum ConnectionState: Equatable, Sendable {
    case disconnected
    case connecting
    case connected
    case buffering(seconds: Int)
    case predicting
    case error(String)
}

@MainActor
protocol PredictionServiceDelegate: AnyObject {
    func service(_ service: PredictionService, didUpdateConnection state: ConnectionState)
    func service(_ service: PredictionService, didReceivePredictions predictions: [String: Double])
    func service(_ service: PredictionService, didReceiveLoading bufferedSeconds: Int)
}

@MainActor
final class PredictionService {
    weak var delegate: PredictionServiceDelegate?

    private let serverURL = URL(string: "ws://192.168.1.184:8000/predict")!
    private let motionSampler = MotionSampler()
    private var webSocket: URLSessionWebSocketTask?
    private var session: URLSession?
    private var sendTask: Task<Void, Never>?
    private var receiveTask: Task<Void, Never>?
    private var isRunning = false

    var connectionState: ConnectionState = .disconnected

    func start() {
        guard !isRunning else { return }
        guard motionSampler.isAvailable else {
            updateState(.error("Accelerometer or gyroscope unavailable on this device."))
            return
        }

        isRunning = true
        updateState(.connecting)

        let config = URLSessionConfiguration.default
        session = URLSession(configuration: config)
        webSocket = session?.webSocketTask(with: serverURL)
        webSocket?.resume()

        receiveTask = Task { @MainActor in
            await self.connectAndRun()
        }
    }

    func stop() {
        isRunning = false
        sendTask?.cancel()
        sendTask = nil
        receiveTask?.cancel()
        receiveTask = nil
        motionSampler.stop()
        webSocket?.cancel(with: .goingAway, reason: nil)
        webSocket = nil
        session?.invalidateAndCancel()
        session = nil
        updateState(.disconnected)
    }

    private func updateState(_ state: ConnectionState) {
        connectionState = state
        delegate?.service(self, didUpdateConnection: state)
    }

    private func connectAndRun() async {
        guard let webSocket else { return }

        do {
            try await ping(webSocket)
        } catch {
            guard isRunning else { return }
            updateState(.error("WebSocket handshake failed: \(error.localizedDescription)"))
            stop()
            return
        }

        guard isRunning else { return }

        motionSampler.start()
        updateState(.connected)
        startSendLoop()

        while !Task.isCancelled, isRunning {
            do {
                let message = try await webSocket.receive()
                handle(message)
            } catch {
                guard isRunning else { return }
                updateState(.error("WebSocket closed: \(error.localizedDescription)"))
                stop()
                return
            }
        }
    }

    private func ping(_ webSocket: URLSessionWebSocketTask) async throws {
        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            webSocket.sendPing { error in
                if let error {
                    continuation.resume(throwing: error)
                } else {
                    continuation.resume()
                }
            }
        }
    }

    private func startSendLoop() {
        sendTask?.cancel()
        sendTask = Task { @MainActor in
            while !Task.isCancelled, isRunning {
                await sendCurrentSecond()
                try? await Task.sleep(for: .seconds(1))
            }
        }
    }

    private func sendCurrentSecond() async {
        guard isRunning, let webSocket else { return }

        let payload = motionSampler.drainPayload()
        guard !payload.accelerometer.isEmpty || !payload.gyroscope.isEmpty else { return }

        guard let data = try? JSONEncoder().encode(payload),
              let text = String(data: data, encoding: .utf8) else { return }

        do {
            try await webSocket.send(.string(text))
        } catch {
            updateState(.error("WebSocket send failed: \(error.localizedDescription)"))
            stop()
        }
    }

    private func handle(_ message: URLSessionWebSocketTask.Message) {
        let data: Data?
        switch message {
        case .string(let text):
            data = text.data(using: .utf8)
        case .data(let blob):
            data = blob
        @unknown default:
            data = nil
        }

        guard let data,
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return }

        if let status = json["status"] as? String, status == "loading",
           let buffered = json["buffered_seconds"] as? Int {
            updateState(.buffering(seconds: buffered))
            delegate?.service(self, didReceiveLoading: buffered)
            return
        }

        if let errorMessage = json["error"] as? String {
            updateState(.error(errorMessage))
            return
        }

        var predictions: [String: Double] = [:]
        for label in PlacementLabel.ordered {
            if let value = json[label.rawValue] as? Double {
                predictions[label.rawValue] = value
            } else if let value = json[label.rawValue] as? NSNumber {
                predictions[label.rawValue] = value.doubleValue
            }
        }

        guard !predictions.isEmpty else { return }

        updateState(.predicting)
        delegate?.service(self, didReceivePredictions: predictions)
    }
}
