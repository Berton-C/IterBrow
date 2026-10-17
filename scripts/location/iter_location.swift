// iter_location — one Core Location fix for Map Station (docs/milestones/M11_browser_track.md A4).
//
// Built by scripts/build_location_helper.sh into ITER_DIR/.runtime/bin/iter_location; main.js runs it
// only when the Map Station page asks. Prints one JSON object and exits:
//   0  {"latitude": …, "longitude": …, "h_accuracy": …, "time": "<ISO 8601>"}
//   2  location access denied (stderr says "denied")
//   3  no fix within 20 s
//   1  any other Core Location error
import CoreLocation
import Foundation

func fail(_ code: Int32, _ message: String) -> Never {
    FileHandle.standardError.write((message + "\n").data(using: .utf8)!)
    exit(code)
}

final class Locator: NSObject, CLLocationManagerDelegate {
    let manager = CLLocationManager()

    override init() {
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyBest
    }

    func start() {
        switch manager.authorizationStatus {
        case .denied, .restricted:
            fail(2, "location access denied")
        case .notDetermined:
            manager.requestWhenInUseAuthorization() // macOS asks once; the answer arrives below
        default:
            manager.requestLocation()
        }
    }

    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        switch manager.authorizationStatus {
        case .denied, .restricted: fail(2, "location access denied")
        case .notDetermined: break
        default: manager.requestLocation()
        }
    }

    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let fix = locations.last else { return }
        let out: [String: Any] = [
            "latitude": fix.coordinate.latitude,
            "longitude": fix.coordinate.longitude,
            "h_accuracy": fix.horizontalAccuracy,
            "time": ISO8601DateFormatter().string(from: fix.timestamp),
        ]
        let data = try! JSONSerialization.data(withJSONObject: out, options: [.sortedKeys])
        FileHandle.standardOutput.write(data)
        FileHandle.standardOutput.write("\n".data(using: .utf8)!)
        exit(0)
    }

    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        if let clError = error as? CLError {
            if clError.code == .denied { fail(2, "location access denied") }
            if clError.code == .locationUnknown { return } // keep waiting until the 20 s deadline
        }
        fail(1, "location error: \(error.localizedDescription)")
    }
}

let locator = Locator()
DispatchQueue.main.asyncAfter(deadline: .now() + 20) { fail(3, "no location fix within 20 s") }
locator.start()
RunLoop.main.run()
