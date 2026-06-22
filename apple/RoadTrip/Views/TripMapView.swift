import SwiftUI
import MapKit

struct TripMapView: View {
    let plan: PlanResponse

    var body: some View {
        Map(initialPosition: .region(region)) {
            Marker(plan.startName, systemImage: "flag.fill", coordinate: plan.startCoord.clLocation)
                .tint(.green)
            ForEach(plan.stops) { stop in
                Marker(stop.name, systemImage: stop.kind.systemImage, coordinate: stop.coord.clLocation)
            }
            Marker(plan.endName, systemImage: "flag.checkered", coordinate: plan.endCoord.clLocation)
                .tint(.red)
        }
        .frame(height: 300)
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }

    /// A region that frames every point on the trip, with a little padding.
    private var region: MKCoordinateRegion {
        let coords = [plan.startCoord.clLocation]
            + plan.stops.map(\.coord.clLocation)
            + [plan.endCoord.clLocation]
        let lats = coords.map(\.latitude)
        let lngs = coords.map(\.longitude)
        let minLat = lats.min() ?? 0, maxLat = lats.max() ?? 0
        let minLng = lngs.min() ?? 0, maxLng = lngs.max() ?? 0
        let center = CLLocationCoordinate2D(
            latitude: (minLat + maxLat) / 2,
            longitude: (minLng + maxLng) / 2
        )
        let span = MKCoordinateSpan(
            latitudeDelta: max((maxLat - minLat) * 1.4, 0.08),
            longitudeDelta: max((maxLng - minLng) * 1.4, 0.08)
        )
        return MKCoordinateRegion(center: center, span: span)
    }
}
