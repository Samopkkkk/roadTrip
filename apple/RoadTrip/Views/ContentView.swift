import SwiftUI

struct ContentView: View {
    @StateObject private var vm = PlanViewModel()
    @AppStorage("backendBaseURL") private var backendBaseURL = "http://localhost:8000"
    @State private var showingSettings = false

    private var baseURL: URL {
        URL(string: backendBaseURL.trimmingCharacters(in: .whitespaces))
            ?? URL(string: "http://localhost:8000")!
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    PlanFormView(request: $vm.request, isLoading: vm.isLoading) {
                        Task { await vm.plan(baseURL: baseURL) }
                    }
                    resultsSection
                }
                .padding()
                .frame(maxWidth: 720)
                .frame(maxWidth: .infinity, alignment: .center)
            }
            .navigationTitle("roadTrip")
            .toolbar {
                ToolbarItem {
                    Button {
                        showingSettings = true
                    } label: {
                        Label("Settings", systemImage: "gearshape")
                    }
                }
            }
            .sheet(isPresented: $showingSettings) {
                SettingsView()
            }
        }
    }

    @ViewBuilder
    private var resultsSection: some View {
        if vm.isLoading {
            VStack(spacing: 12) {
                ProgressView()
                Text("Planning your trip…")
                    .foregroundStyle(.secondary)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 40)
        } else if let message = vm.errorMessage {
            StatusCard(
                systemImage: "exclamationmark.triangle.fill",
                tint: .orange,
                title: "Couldn't build a plan",
                message: message
            )
        } else if let result = vm.result {
            PlanResultView(plan: result)
        } else {
            StatusCard(
                systemImage: "map",
                tint: .accentColor,
                title: "Where to?",
                message: "Give a destination, an attraction, a direction to wander, or just an idea — and we'll plan the whole trip with stops and a cost estimate."
            )
        }
    }
}

#Preview {
    ContentView()
}
