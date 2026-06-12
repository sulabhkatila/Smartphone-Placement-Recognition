import SwiftUI

struct ContentView: View {
    @State private var viewModel = PhonePlacementViewModel()

    var body: some View {
        ZStack {
            background

            ScrollView(.vertical, showsIndicators: false) {
                VStack(spacing: 22) {
                    header
                    PlacementHeroView(
                        placement: viewModel.topPlacement,
                        confidence: viewModel.topConfidence,
                        state: viewModel.connectionState,
                        bufferProgress: viewModel.bufferProgress
                    )
                    probabilityStrip
                    terminalSection
                }
                .padding(.horizontal, 20)
                .padding(.top, 12)
                .padding(.bottom, 100)
            }

            VStack {
                Spacer()
                controlBar
            }
        }
        .preferredColorScheme(.dark)
    }

    private var background: some View {
        ZStack {
            Color(red: 0.04, green: 0.05, blue: 0.08)
                .ignoresSafeArea()

            Circle()
                .fill(
                    RadialGradient(
                        colors: [
                            (viewModel.topPlacement?.accent ?? .cyan).opacity(0.28),
                            .clear
                        ],
                        center: .center,
                        startRadius: 20,
                        endRadius: 260
                    )
                )
                .frame(width: 420, height: 420)
                .offset(y: -180)
                .blur(radius: 8)
                .animation(.easeInOut(duration: 0.8), value: viewModel.topPlacement?.id)

            Circle()
                .fill(
                    RadialGradient(
                        colors: [Color.purple.opacity(0.15), .clear],
                        center: .center,
                        startRadius: 10,
                        endRadius: 200
                    )
                )
                .frame(width: 360, height: 360)
                .offset(x: 120, y: 320)
                .blur(radius: 12)
        }
    }

    private var header: some View {
        HStack(alignment: .top) {
            VStack(alignment: .leading, spacing: 4) {
                Text("WhereMyPhoneAt")
                    .font(.system(size: 22, weight: .bold, design: .rounded))
                    .foregroundStyle(.white)
                Text("Real-time placement inference")
                    .font(.system(size: 13, weight: .medium, design: .rounded))
                    .foregroundStyle(Color.white.opacity(0.45))
            }
            Spacer()
            Image(systemName: "iphone.radiowaves.left.and.right")
                .font(.system(size: 22, weight: .semibold))
                .foregroundStyle(
                    LinearGradient(
                        colors: [.cyan, .purple],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .symbolEffect(.variableColor.iterative, isActive: viewModel.isActive)
        }
    }

    private var probabilityStrip: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("ALL PLACEMENTS")
                .font(.system(size: 11, weight: .bold, design: .monospaced))
                .foregroundStyle(Color.white.opacity(0.4))
                .tracking(1.2)

            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
                ForEach(PlacementLabel.ordered) { label in
                    PlacementChip(
                        label: label,
                        probability: viewModel.predictions[label.rawValue] ?? 0,
                        isTop: viewModel.topPlacement == label
                    )
                }
            }
        }
    }

    private var terminalSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("RAW RESPONSE")
                    .font(.system(size: 11, weight: .bold, design: .monospaced))
                    .foregroundStyle(Color.white.opacity(0.4))
                    .tracking(1.2)
                Spacer()
                Text("192.168.1.184:8000")
                    .font(.system(size: 10, weight: .medium, design: .monospaced))
                    .foregroundStyle(Color.green.opacity(0.55))
            }

            TerminalJSONView(predictions: viewModel.predictions)
        }
    }

    private var controlBar: some View {
        HStack(spacing: 14) {
            VStack(alignment: .leading, spacing: 2) {
                Text(viewModel.isActive ? "Streaming IMU" : "Ready")
                    .font(.system(size: 13, weight: .semibold, design: .rounded))
                    .foregroundStyle(.white)
                Text("1 Hz · 100 Hz sensors · 10s window")
                    .font(.system(size: 11, weight: .medium, design: .monospaced))
                    .foregroundStyle(Color.white.opacity(0.4))
            }

            Spacer()

            Button(action: { viewModel.toggleSession() }) {
                HStack(spacing: 8) {
                    Image(systemName: viewModel.isActive ? "stop.fill" : "play.fill")
                        .font(.system(size: 13, weight: .bold))
                    Text(viewModel.isActive ? "Stop" : "Start")
                        .font(.system(size: 15, weight: .bold, design: .rounded))
                }
                .foregroundStyle(.white)
                .padding(.horizontal, 22)
                .padding(.vertical, 14)
                .background(
                    Capsule()
                        .fill(
                            LinearGradient(
                                colors: viewModel.isActive
                                    ? [Color(red: 0.95, green: 0.32, blue: 0.32), Color(red: 0.75, green: 0.18, blue: 0.28)]
                                    : [Color(red: 0.22, green: 0.78, blue: 0.95), Color(red: 0.45, green: 0.38, blue: 0.98)],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            )
                        )
                )
                .shadow(color: (viewModel.isActive ? Color.red : Color.cyan).opacity(0.35), radius: 14, y: 6)
            }
            .buttonStyle(.plain)
        }
        .padding(.horizontal, 22)
        .padding(.vertical, 16)
        .background(
            RoundedRectangle(cornerRadius: 22, style: .continuous)
                .fill(.ultraThinMaterial)
                .overlay(
                    RoundedRectangle(cornerRadius: 22, style: .continuous)
                        .strokeBorder(Color.white.opacity(0.08), lineWidth: 1)
                )
                .shadow(color: .black.opacity(0.4), radius: 20, y: -4)
        )
        .padding(.horizontal, 16)
        .padding(.bottom, 10)
    }
}

private struct PlacementChip: View {
    let label: PlacementLabel
    let probability: Double
    let isTop: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                Image(systemName: label.icon)
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(label.accent)
                Text(label.rawValue)
                    .font(.system(size: 12, weight: .bold, design: .monospaced))
                    .foregroundStyle(Color.white.opacity(0.85))
                Spacer()
                if isTop {
                    Image(systemName: "crown.fill")
                        .font(.system(size: 10))
                        .foregroundStyle(.yellow)
                }
            }

            Text(String(format: "%.1f%%", probability * 100))
                .font(.system(size: 18, weight: .bold, design: .rounded))
                .foregroundStyle(.white)

            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    Capsule().fill(Color.white.opacity(0.08))
                    Capsule()
                        .fill(label.accent.opacity(isTop ? 1 : 0.65))
                        .frame(width: geo.size.width * probability)
                }
            }
            .frame(height: 4)
        }
        .padding(12)
        .background(
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .fill(Color.white.opacity(isTop ? 0.08 : 0.04))
                .overlay(
                    RoundedRectangle(cornerRadius: 14, style: .continuous)
                        .strokeBorder(
                            isTop ? label.accent.opacity(0.55) : Color.white.opacity(0.06),
                            lineWidth: isTop ? 1.5 : 1
                        )
                )
        )
        .animation(.spring(response: 0.4, dampingFraction: 0.82), value: probability)
    }
}

#Preview {
    ContentView()
}
