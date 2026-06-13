import SwiftUI

struct PlanResultView: View {
    let plan: PlanResponse

    private var daySections: [(day: Int, stops: [PlanStop])] {
        Dictionary(grouping: plan.stops, by: \.day)
            .map { (day: $0.key, stops: $0.value.sorted { $0.order < $1.order }) }
            .sorted { $0.day < $1.day }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 22) {
            header
            statTiles

            if plan.originAssumed {
                Callout(
                    systemImage: "location.circle",
                    text: "No starting point set, so this is planned around the destination and the cost excludes the drive there. Add an origin for a door-to-door estimate."
                )
            }

            TripMapView(plan: plan)

            section("Cost estimate", systemImage: "dollarsign.circle") {
                CostBreakdownView(costs: plan.costs)
            }

            section("Itinerary", systemImage: "list.bullet") {
                VStack(alignment: .leading, spacing: 16) {
                    ForEach(daySections, id: \.day) { day, stops in
                        VStack(alignment: .leading, spacing: 2) {
                            Text("Day \(day)")
                                .font(.subheadline.weight(.bold))
                                .foregroundStyle(.tint)
                            ForEach(stops) { StopRow(stop: $0) }
                        }
                    }
                }
            }

            if !plan.legs.isEmpty {
                LegsView(legs: plan.legs)
            }

            if !plan.warnings.isEmpty {
                section("Notes", systemImage: "info.circle") {
                    VStack(alignment: .leading, spacing: 6) {
                        ForEach(plan.warnings, id: \.self) { warning in
                            Text("• \(warning)")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .firstTextBaseline) {
                Text(plan.title).font(.title2.bold())
                Spacer()
                Chip(text: plan.isLLM ? "AI plan" : "Quick plan",
                     systemImage: plan.isLLM ? "sparkles" : "bolt.fill")
            }
            Text(plan.summary).foregroundStyle(.secondary)
            if !plan.tags.isEmpty {
                FlowLayout(spacing: 6) {
                    ForEach(plan.tags, id: \.self) { Chip(text: $0) }
                }
            }
        }
    }

    private var statTiles: some View {
        HStack(spacing: 10) {
            StatTile(systemImage: "road.lanes", title: "Distance",
                     value: Format.km(meters: plan.distanceMeters))
            StatTile(systemImage: "clock", title: "Drive time",
                     value: Format.duration(seconds: plan.expectedTravelTimeSeconds))
            StatTile(systemImage: "creditcard", title: "Total",
                     value: Format.usd(plan.costs.totalUsd))
        }
    }

    @ViewBuilder
    private func section<Content: View>(
        _ title: String, systemImage: String, @ViewBuilder content: () -> Content
    ) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Label(title, systemImage: systemImage)
                .font(.headline)
            content()
        }
    }
}

private struct StopRow: View {
    let stop: PlanStop

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: stop.kind.systemImage)
                .frame(width: 22)
                .foregroundStyle(.tint)
                .padding(.top, 2)
            VStack(alignment: .leading, spacing: 3) {
                HStack(alignment: .firstTextBaseline) {
                    Text(stop.name).font(.subheadline.weight(.semibold))
                    Spacer()
                    if let arrival = stop.arrivalLocal {
                        Text(arrival).font(.caption).foregroundStyle(.secondary)
                    }
                }
                HStack(spacing: 6) {
                    Text(stop.kind.label)
                    if stop.durationMinutes > 0 {
                        Text("· \(Format.duration(seconds: Double(stop.durationMinutes) * 60))")
                    }
                }
                .font(.caption2)
                .foregroundStyle(.secondary)
                if let notes = stop.notes, !notes.isEmpty {
                    Text(notes).font(.caption).foregroundStyle(.secondary)
                }
            }
        }
        .padding(.vertical, 6)
    }
}

private struct CostBreakdownView: View {
    let costs: CostBreakdown
    @State private var showAssumptions = false

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            row("Fuel", costs.fuelUsd, "fuelpump.fill")
            row("Lodging", costs.lodgingUsd, "bed.double.fill")
            row("Food", costs.foodUsd, "fork.knife")
            row("Activities", costs.activitiesUsd, "ticket.fill")
            Divider()
            HStack {
                Text("Total").font(.headline)
                Spacer()
                Text(Format.usd(costs.totalUsd)).font(.headline)
            }
            HStack {
                Text("Per person").foregroundStyle(.secondary)
                Spacer()
                Text(Format.usd(costs.perPersonUsd)).foregroundStyle(.secondary)
            }
            if !costs.assumptions.isEmpty {
                DisclosureGroup("How we estimated this", isExpanded: $showAssumptions) {
                    VStack(alignment: .leading, spacing: 4) {
                        ForEach(costs.assumptions, id: \.self) { line in
                            Text("• \(line)").font(.caption).foregroundStyle(.secondary)
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.top, 4)
                }
                .font(.caption)
                .tint(.secondary)
            }
        }
    }

    private func row(_ label: String, _ value: Double, _ icon: String) -> some View {
        HStack {
            Label(label, systemImage: icon)
            Spacer()
            Text(Format.usd(value))
        }
        .font(.subheadline)
    }
}

private struct LegsView: View {
    let legs: [RouteLeg]
    @State private var expanded = false

    var body: some View {
        DisclosureGroup("Drive legs (\(legs.count))", isExpanded: $expanded) {
            VStack(alignment: .leading, spacing: 6) {
                ForEach(legs) { leg in
                    HStack {
                        Text("\(leg.fromName ?? "Start") → \(leg.toName ?? "End")")
                            .font(.caption)
                            .lineLimit(1)
                        Spacer()
                        Text("\(Format.km(meters: leg.distanceMeters)) · \(Format.duration(seconds: leg.durationSeconds))")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.top, 4)
        }
        .font(.headline)
    }
}
