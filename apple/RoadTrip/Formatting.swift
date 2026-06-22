import SwiftUI

// MARK: - Optional-string binding helper

extension Binding where Value == String? {
    /// Bridges an optional String to a `TextField`: empty input becomes nil.
    func orEmpty() -> Binding<String> {
        Binding<String>(
            get: { wrappedValue ?? "" },
            set: { wrappedValue = $0.isEmpty ? nil : $0 }
        )
    }
}

// MARK: - Display formatting

enum Format {
    static func usd(_ value: Double) -> String {
        value.formatted(.currency(code: "USD").precision(.fractionLength(0)))
    }

    /// Distance in kilometres, e.g. "1,234 km".
    static func km(meters: Double) -> String {
        let km = meters / 1000.0
        return "\(km.formatted(.number.precision(.fractionLength(0)))) km"
    }

    /// Distance shown as "1,234 km · 767 mi".
    static func distance(meters: Double) -> String {
        let km = meters / 1000.0
        let mi = meters / 1609.344
        return "\(km.formatted(.number.precision(.fractionLength(0)))) km · \(mi.formatted(.number.precision(.fractionLength(0)))) mi"
    }

    /// Duration shown as "12h 30m" (or "45m").
    static func duration(seconds: Double) -> String {
        let total = Int(seconds.rounded())
        let hours = total / 3600
        let minutes = (total % 3600) / 60
        if hours == 0 { return "\(minutes)m" }
        if minutes == 0 { return "\(hours)h" }
        return "\(hours)h \(minutes)m"
    }
}
