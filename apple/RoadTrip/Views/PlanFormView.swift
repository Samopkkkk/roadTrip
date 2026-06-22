import SwiftUI

struct PlanFormView: View {
    @Binding var request: PlanRequest
    var isLoading: Bool
    var onSubmit: () -> Void

    var body: some View {
        VStack(spacing: 16) {
            GroupBox {
                VStack(alignment: .leading, spacing: 10) {
                    Text("Your idea")
                        .font(.headline)
                    TextField(
                        "e.g. road trip from San Francisco to Seattle",
                        text: $request.idea,
                        axis: .vertical
                    )
                    .textFieldStyle(.roundedBorder)
                    .lineLimit(1...3)
                    Text("Or fill in any of the details below — anything works.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }

            GroupBox {
                VStack(alignment: .leading, spacing: 12) {
                    labeledField("Destination", text: $request.destination.orEmpty(),
                                 placeholder: "Grand Canyon")
                    labeledField("Must-see attraction", text: $request.anchorAttraction.orEmpty(),
                                 placeholder: "Yosemite")
                    labeledField("Origin", text: $request.origin.orEmpty(),
                                 placeholder: "Denver")
                    labeledField("Direction to wander", text: $request.direction.orEmpty(),
                                 placeholder: "north")
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }

            GroupBox {
                VStack(spacing: 14) {
                    Stepper(value: $request.days, in: 1...60) {
                        labelValue("Days", "\(request.days)")
                    }
                    Stepper(value: $request.partySize, in: 1...20) {
                        labelValue("Travelers", "\(request.partySize)")
                    }
                    VStack(alignment: .leading, spacing: 6) {
                        Text("Pace").font(.subheadline).foregroundStyle(.secondary)
                        Picker("Pace", selection: $request.pace) {
                            ForEach(Pace.allCases) { Text($0.label).tag($0) }
                        }
                        .pickerStyle(.segmented)
                        .labelsHidden()
                    }
                    Toggle(isOn: $request.roundTrip) {
                        labelValue("Round trip", request.roundTrip ? "Yes" : "One-way")
                    }
                }
            }

            Button(action: onSubmit) {
                HStack {
                    Image(systemName: "wand.and.stars")
                    Text("Plan my trip")
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 6)
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .disabled(!request.hasSeed || isLoading)
        }
    }

    private func labeledField(_ label: String, text: Binding<String>, placeholder: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label).font(.subheadline).foregroundStyle(.secondary)
            TextField(placeholder, text: text)
                .textFieldStyle(.roundedBorder)
                #if os(iOS)
                .autocorrectionDisabled()
                .textInputAutocapitalization(.words)
                #endif
        }
    }

    private func labelValue(_ label: String, _ value: String) -> some View {
        HStack {
            Text(label)
            Spacer()
            Text(value).foregroundStyle(.secondary)
        }
    }
}
