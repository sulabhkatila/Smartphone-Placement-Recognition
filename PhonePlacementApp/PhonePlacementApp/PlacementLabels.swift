import SwiftUI

enum PlacementLabel: String, CaseIterable, Identifiable {
    case lb = "LB"
    case hand = "H"
    case backPocket = "BP"
    case frontPocket = "FP"
    case coatPocket = "CP"
    case shoulderBag = "SB"

    var id: String { rawValue }

    var title: String {
        switch self {
        case .lb: "Lower Back"
        case .hand: "Hand-held"
        case .backPocket: "Back Pocket"
        case .frontPocket: "Front Pocket"
        case .coatPocket: "Coat Pocket"
        case .shoulderBag: "Shoulder Bag"
        }
    }

    var subtitle: String {
        switch self {
        case .lb: "Belt-fixed at L5, landscape"
        case .hand: "Natural arm swing"
        case .backPocket: "Trousers rear pocket"
        case .frontPocket: "Trousers front pocket"
        case .coatPocket: "Jacket side pocket"
        case .shoulderBag: "Carried in bag"
        }
    }

    var icon: String {
        switch self {
        case .lb: "figure.stand"
        case .hand: "hand.raised.fill"
        case .backPocket: "rectangle.portrait.bottomhalf.inset.filled"
        case .frontPocket: "rectangle.portrait.bottomhalf.filled"
        case .coatPocket: "jacket.fill"
        case .shoulderBag: "bag.fill"
        }
    }

    var accent: Color {
        switch self {
        case .lb: Color(red: 0.55, green: 0.36, blue: 0.96)
        case .hand: Color(red: 0.20, green: 0.78, blue: 0.95)
        case .backPocket: Color(red: 0.98, green: 0.45, blue: 0.35)
        case .frontPocket: Color(red: 0.99, green: 0.72, blue: 0.28)
        case .coatPocket: Color(red: 0.38, green: 0.85, blue: 0.55)
        case .shoulderBag: Color(red: 0.95, green: 0.55, blue: 0.75)
        }
    }

    static let ordered: [PlacementLabel] = [.lb, .hand, .backPocket, .frontPocket, .coatPocket, .shoulderBag]
}
