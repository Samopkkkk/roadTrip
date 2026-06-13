import SwiftUI

struct SettingsView: View {
    @Environment(\.dismiss) private var dismiss
    @AppStorage("backendBaseURL") private var backendBaseURL = "http://localhost:8000"

    var body: some View {
        NavigationStack {
            Form {
                Section("Backend") {
                    TextField("http://localhost:8000", text: $backendBaseURL)
                        #if os(iOS)
                        .keyboardType(.URL)
                        .autocorrectionDisabled()
                        .textInputAutocapitalization(.never)
                        #endif
                    Button("Reset to localhost") {
                        backendBaseURL = "http://localhost:8000"
                    }
                }
                Section {
                    Text("The planner API. Run it locally with `uvicorn backend.app.main:app` (default port 8000), or point this at a deployed instance.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            .navigationTitle("Settings")
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
        #if os(macOS)
        .frame(minWidth: 420, minHeight: 240)
        #endif
    }
}
