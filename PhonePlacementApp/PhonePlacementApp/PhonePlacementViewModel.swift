import Foundation
import SwiftUI

private let defaultPredictions: [String: Double] = Dictionary(
    uniqueKeysWithValues: PlacementLabel.ordered.map { ($0.rawValue, 0.0) }
)

@MainActor
@Observable
final class PhonePlacementViewModel: PredictionServiceDelegate {
    var connectionState: ConnectionState = .disconnected
    var predictions: [String: Double] = defaultPredictions
    var bufferedSeconds: Int = 0
    var isActive = false

    private let service = PredictionService()

    var topPlacement: PlacementLabel? {
        guard case .predicting = connectionState else { return nil }
        let best = predictions.max(by: { $0.value < $1.value })
        guard let key = best?.key, let label = PlacementLabel(rawValue: key), best?.value ?? 0 > 0 else {
            return nil
        }
        return label
    }

    var topConfidence: Double {
        guard let topPlacement else { return 0 }
        return predictions[topPlacement.rawValue] ?? 0
    }

    var bufferProgress: Double {
        min(Double(bufferedSeconds) / 10.0, 1.0)
    }

    init() {
        service.delegate = self
    }

    func toggleSession() {
        if isActive {
            stop()
        } else {
            start()
        }
    }

    func start() {
        isActive = true
        predictions = defaultPredictions
        bufferedSeconds = 0
        service.start()
    }

    func stop() {
        isActive = false
        service.stop()
        connectionState = .disconnected
        bufferedSeconds = 0
    }

    func service(_ service: PredictionService, didUpdateConnection state: ConnectionState) {
        connectionState = state
    }

    func service(_ service: PredictionService, didReceivePredictions predictions: [String: Double]) {
        withAnimation(.spring(response: 0.45, dampingFraction: 0.82)) {
            for label in PlacementLabel.ordered {
                self.predictions[label.rawValue] = predictions[label.rawValue] ?? 0
            }
        }
    }

    func service(_ service: PredictionService, didReceiveLoading bufferedSeconds: Int) {
        withAnimation(.easeInOut(duration: 0.3)) {
            self.bufferedSeconds = bufferedSeconds
        }
    }
}
