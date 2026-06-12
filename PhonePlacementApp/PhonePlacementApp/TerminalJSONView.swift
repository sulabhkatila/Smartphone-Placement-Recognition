import SwiftUI

struct TerminalJSONView: View {
    let predictions: [String: Double]

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            terminalChrome
            ScrollView(.vertical, showsIndicators: false) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("{")
                        .terminalToken(.brace)
                    ForEach(Array(PlacementLabel.ordered.enumerated()), id: \.element.id) { index, label in
                        HStack(spacing: 0) {
                            Text("  \"")
                                .terminalToken(.brace)
                            Text(label.rawValue)
                                .terminalToken(.key)
                            Text("\": ")
                                .terminalToken(.brace)
                            Text(formattedValue(predictions[label.rawValue] ?? 0))
                                .terminalToken(.number)
                            if index < PlacementLabel.ordered.count - 1 {
                                Text(",")
                                    .terminalToken(.brace)
                            }
                        }
                        .font(.system(size: 13, weight: .regular, design: .monospaced))
                    }
                    Text("}")
                        .terminalToken(.brace)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, 14)
                .padding(.vertical, 12)
            }
        }
        .background(
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .fill(Color(red: 0.08, green: 0.09, blue: 0.11))
                .overlay(
                    RoundedRectangle(cornerRadius: 14, style: .continuous)
                        .strokeBorder(Color.white.opacity(0.06), lineWidth: 1)
                )
        )
        .shadow(color: .black.opacity(0.35), radius: 16, y: 8)
    }

    private var terminalChrome: some View {
        HStack(spacing: 7) {
            Circle().fill(Color(red: 1, green: 0.37, blue: 0.34)).frame(width: 10, height: 10)
            Circle().fill(Color(red: 1, green: 0.74, blue: 0.18)).frame(width: 10, height: 10)
            Circle().fill(Color(red: 0.16, green: 0.84, blue: 0.37)).frame(width: 10, height: 10)
            Spacer()
            Text("predict → response.json")
                .font(.system(size: 11, weight: .medium, design: .monospaced))
                .foregroundStyle(Color.white.opacity(0.35))
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .background(Color.black.opacity(0.35))
    }

    private func formattedValue(_ value: Double) -> String {
        String(format: "%.5f", value)
    }
}

private enum TerminalToken {
    case brace, key, number
}

private extension Text {
    func terminalToken(_ token: TerminalToken) -> Text {
        switch token {
        case .brace:
            self.foregroundStyle(Color(red: 0.72, green: 0.74, blue: 0.78))
        case .key:
            self.foregroundStyle(Color(red: 0.56, green: 0.84, blue: 0.98))
        case .number:
            self.foregroundStyle(Color(red: 0.98, green: 0.55, blue: 0.38))
        }
    }
}
