import Foundation
import CoreLocation

// MARK: - Request

/// Mirrors the backend `PlanRequest`. Optionals are omitted from JSON when nil
/// (Swift's synthesised `Encodable` uses `encodeIfPresent`), matching the API.
struct PlanRequest: Codable {
    var idea: String = ""
    var origin: String?
    var destination: String?
    var anchorAttraction: String?
    var direction: String?
    var days: Int = 3
    var partySize: Int = 2
    var pace: Pace = .balanced
    var roundTrip: Bool = false

    /// The API requires at least one "seed" — an idea, destination, attraction,
    /// or direction. Used to enable/disable the submit button.
    var hasSeed: Bool {
        [idea, origin, destination, anchorAttraction, direction]
            .compactMap { $0 }
            .contains { !$0.trimmingCharacters(in: .whitespaces).isEmpty }
    }
}

enum Pace: String, Codable, CaseIterable, Identifiable {
    case relaxed, balanced, packed
    var id: String { rawValue }
    var label: String { rawValue.capitalized }
}

// MARK: - Response

struct PlanResponse: Codable, Hashable {
    let title: String
    let summary: String
    let tags: [String]
    let startName: String
    let startCoord: Coordinate
    let endName: String
    let endCoord: Coordinate
    let distanceMeters: Double
    let expectedTravelTimeSeconds: Double
    let stops: [PlanStop]
    let legs: [RouteLeg]
    let costs: CostBreakdown
    let source: String
    let originAssumed: Bool
    let warnings: [String]

    var isLLM: Bool { source == "llm" }
}

struct Coordinate: Codable, Hashable {
    let lat: Double
    let lng: Double
    var clLocation: CLLocationCoordinate2D { .init(latitude: lat, longitude: lng) }
}

struct PlanStop: Codable, Identifiable, Hashable {
    let day: Int
    let order: Int
    let name: String
    let kind: StopKind
    let coord: Coordinate
    let arrivalLocal: String?
    let durationMinutes: Int
    let notes: String?

    var id: String { "\(day)-\(order)-\(name)" }
}

enum StopKind: String, Codable {
    case attraction, scenic, activity, food, lodging, fuel, rest

    // Tolerate any unknown kind the backend might add later.
    init(from decoder: Decoder) throws {
        let raw = try decoder.singleValueContainer().decode(String.self)
        self = StopKind(rawValue: raw.lowercased()) ?? .attraction
    }

    var label: String { rawValue.capitalized }

    var systemImage: String {
        switch self {
        case .attraction: return "star.fill"
        case .scenic: return "binoculars.fill"
        case .activity: return "figure.hiking"
        case .food: return "fork.knife"
        case .lodging: return "bed.double.fill"
        case .fuel: return "fuelpump.fill"
        case .rest: return "cup.and.saucer.fill"
        }
    }
}

struct RouteLeg: Codable, Identifiable, Hashable {
    let fromName: String?
    let toName: String?
    let distanceMeters: Double
    let durationSeconds: Double

    var id: String { "\(fromName ?? "?")->\(toName ?? "?")-\(Int(distanceMeters))" }
}

struct CostBreakdown: Codable, Hashable {
    let fuelUsd: Double
    let lodgingUsd: Double
    let foodUsd: Double
    let activitiesUsd: Double
    let totalUsd: Double
    let perPersonUsd: Double
    let assumptions: [String]
}
