import SwiftUI

struct PlacementHeroView: View {
    let placement: PlacementLabel?
    let confidence: Double
    let state: ConnectionState
    let bufferProgress: Double

    @State private var pulse = false
    @State private var ringRotation: Double = 0

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 28, style: .continuous)
                .fill(
                    LinearGradient(
                        colors: heroGradient,
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .overlay(
                    RoundedRectangle(cornerRadius: 28, style: .continuous)
                        .strokeBorder(Color.white.opacity(0.12), lineWidth: 1)
                )
                .shadow(color: glowColor.opacity(0.45), radius: 28, y: 12)

            VStack(spacing: 18) {
                statusPill

                ZStack {
                    if case .buffering = state {
                        Circle()
                            .trim(from: 0, to: bufferProgress)
                            .stroke(
                                AngularGradient(
                                    colors: [.cyan, .purple, .cyan],
                                    center: .center
                                ),
                                style: StrokeStyle(lineWidth: 4, lineCap: .round)
                            )
                            .frame(width: 132, height: 132)
                            .rotationEffect(.degrees(-90))
                            .animation(.easeInOut(duration: 0.5), value: bufferProgress)
                    }

                    Circle()
                        .fill(Color.black.opacity(0.22))
                        .frame(width: 118, height: 118)
                        .overlay(
                            Circle()
                                .strokeBorder(Color.white.opacity(0.08), lineWidth: 1)
                        )

                    Image(systemName: heroIcon)
                        .font(.system(size: 46, weight: .semibold))
                        .foregroundStyle(.white)
                        .symbolEffect(.pulse, options: .repeating, isActive: pulse && placement != nil)
                        .scaleEffect(pulse && placement != nil ? 1.04 : 1)
                        .animation(.easeInOut(duration: 1.4).repeatForever(autoreverses: true), value: pulse)
                }

                VStack(spacing: 6) {
                    Text(heroTitle)
                        .font(.system(size: 28, weight: .bold, design: .rounded))
                        .foregroundStyle(.white)
                        .multilineTextAlignment(.center)

                    Text(heroSubtitle)
                        .font(.system(size: 14, weight: .medium, design: .rounded))
                        .foregroundStyle(Color.white.opacity(0.72))
                        .multilineTextAlignment(.center)
                }

                if placement != nil {
                    confidenceBar
                }
            }
            .padding(24)
        }
        .frame(maxWidth: .infinity)
        .onAppear {
            pulse = true
        }
        .onChange(of: placement?.id) { _, _ in
            withAnimation(.spring(response: 0.5, dampingFraction: 0.7)) {
                ringRotation += 45
            }
        }
    }

    private var statusPill: some View {
        HStack(spacing: 6) {
            Circle()
                .fill(statusColor)
                .frame(width: 7, height: 7)
            Text(statusText)
                .font(.system(size: 11, weight: .semibold, design: .monospaced))
                .foregroundStyle(Color.white.opacity(0.85))
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 6)
        .background(Capsule().fill(Color.black.opacity(0.28)))
    }

    private var confidenceBar: some View {
        VStack(spacing: 8) {
            HStack {
                Text("CONFIDENCE")
                    .font(.system(size: 10, weight: .bold, design: .monospaced))
                    .foregroundStyle(Color.white.opacity(0.5))
                Spacer()
                Text(String(format: "%.1f%%", confidence * 100))
                    .font(.system(size: 12, weight: .bold, design: .monospaced))
                    .foregroundStyle(.white)
            }

            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    Capsule()
                        .fill(Color.white.opacity(0.12))
                    Capsule()
                        .fill(
                            LinearGradient(
                                colors: [placement?.accent ?? .cyan, .white.opacity(0.9)],
                                startPoint: .leading,
                                endPoint: .trailing
                            )
                        )
                        .frame(width: geo.size.width * confidence)
                        .animation(.spring(response: 0.5, dampingFraction: 0.8), value: confidence)
                }
            }
            .frame(height: 6)
        }
    }

    private var heroIcon: String {
        placement?.icon ?? "waveform.path.ecg"
    }

    private var heroTitle: String {
        switch state {
        case .disconnected:
            "Where's My Phone?"
        case .connecting:
            "Connecting…"
        case .connected, .buffering:
            "Calibrating Motion"
        case .predicting:
            placement?.title ?? "Analyzing…"
        case .error:
            "Connection Error"
        }
    }

    private var heroSubtitle: String {
        switch state {
        case .disconnected:
            "Tap start to stream IMU data"
        case .connecting:
            "ws://192.168.1.184:8000/predict"
        case .connected:
            "Buffering sensor window…"
        case .buffering(let seconds):
            "Collecting \(seconds)/10 seconds of gait data"
        case .predicting:
            placement?.subtitle ?? "Live placement inference"
        case .error(let message):
            message
        }
    }

    private var statusText: String {
        switch state {
        case .disconnected: "OFFLINE"
        case .connecting: "CONNECTING"
        case .connected: "STREAMING"
        case .buffering: "BUFFERING"
        case .predicting: "LIVE"
        case .error: "ERROR"
        }
    }

    private var statusColor: Color {
        switch state {
        case .disconnected: .gray
        case .connecting: .yellow
        case .connected, .buffering: .orange
        case .predicting: .green
        case .error: .red
        }
    }

    private var heroGradient: [Color] {
        if let placement {
            [
                placement.accent.opacity(0.85),
                placement.accent.opacity(0.45),
                Color(red: 0.12, green: 0.13, blue: 0.18)
            ]
        } else {
            [
                Color(red: 0.18, green: 0.22, blue: 0.32),
                Color(red: 0.10, green: 0.11, blue: 0.15)
            ]
        }
    }

    private var glowColor: Color {
        placement?.accent ?? Color(red: 0.3, green: 0.5, blue: 0.9)
    }
}
