# roadTrip — iOS & macOS app

A SwiftUI **multiplatform** client for the roadTrip planner. One codebase, one
target, runs on both iPhone/iPad (iOS 17+) and Mac (macOS 14+). You type an idea
(or a destination / attraction / direction), and it calls the backend's
`POST /plan` and shows the itinerary on a map with a cost breakdown.

> Authored on Linux without an Xcode toolchain, so it ships as source — open it
> in **Xcode 16+** to build and run.

## Run it

**1. Start the backend** (from the repo root):

```bash
pip install -r backend/requirements.txt
uvicorn backend.app.main:app            # serves http://localhost:8000
# (set ANTHROPIC_API_KEY first if you want the LLM planner; otherwise it uses
#  the offline heuristic planner automatically)
```

**2. Generate the Xcode project and open it:**

```bash
brew install xcodegen
cd apple
xcodegen generate
open RoadTrip.xcodeproj
```

Pick **My Mac** or an **iOS Simulator** in the scheme selector and hit Run.

### No XcodeGen? Create the project by hand (≈2 min)

1. Xcode → File → New → Project → **Multiplatform → App**. Name it `RoadTrip`,
   uncheck tests/Core Data.
2. Delete the template's `RoadTripApp.swift` and `ContentView.swift`.
3. Drag the `apple/RoadTrip/` folder into the project navigator ("Create groups",
   add to the RoadTrip target).
4. Set both deployment targets: iOS **17.0**, macOS **14.0**.
5. In the target's Info, add **App Transport Security Settings → Allow Local
   Networking = YES** (so it can reach `http://localhost`).

## Configure the backend URL

Tap/click the **gear** (toolbar) → set the backend URL. Defaults to
`http://localhost:8000`. Point it at a deployed instance when you have one.

- **iOS Simulator** reaches your Mac's `localhost` directly — no change needed.
- **Physical iPhone**: use your Mac's LAN IP (e.g. `http://192.168.1.x:8000`) and
  make sure the phone is on the same network.
- **macOS**: this dev build is unsandboxed so localhost works out of the box. If
  you enable the App Sandbox for distribution, also enable **Outgoing Connections
  (Client)**.

## What's inside

```
apple/
  project.yml                 # XcodeGen spec (multiplatform app target)
  RoadTrip/
    RoadTripApp.swift         # @main App
    Models.swift              # Codable mirror of the backend contract
    PlanService.swift         # async POST /plan + typed errors
    PlanViewModel.swift       # @MainActor state (request / result / loading / error)
    Formatting.swift          # currency / distance / duration helpers
    Views/
      ContentView.swift       # form + results, loading / error / empty states
      PlanFormView.swift      # idea, destination, origin, direction, days, pace…
      PlanResultView.swift    # summary, stats, cost breakdown, day-by-day itinerary
      TripMapView.swift       # MapKit map auto-framed to all stops
      SupportingViews.swift   # chips, stat tiles, callouts, flow layout
      SettingsView.swift      # backend URL
```

The app reads `origin_assumed` to nudge the traveler to set a start, shows the
`source` ("AI plan" vs "Quick plan"), and renders the per-leg `legs[]` breakdown
— all fields the backend already returns.
