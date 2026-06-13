import SwiftUI

@main
struct RoadTripApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        #if os(macOS)
        .defaultSize(width: 960, height: 760)
        .windowResizability(.contentMinSize)
        #endif
    }
}
