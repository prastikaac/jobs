import Foundation

// MARK: - AppUpdateChecker

/// Checks whether the installed app version is behind the latest App Store release
/// by querying the public iTunes Lookup API (no API key required).
///
/// Usage:
///   AppUpdateChecker.shared.checkForUpdate { result in
///       switch result {
///       case .updateRequired(let storeVersion, let storeURL):
///           // show mandatory update screen
///       case .upToDate:
///           // continue normally
///       case .unavailable:
///           // App Store not reachable or app not found — continue normally
///       }
///   }
final class AppUpdateChecker {

    static let shared = AppUpdateChecker()
    private init() {}

    // Bundle ID of this app — must match exactly what is on the App Store.
    private let bundleID = "fi.findjobsinfinland.app"

    enum UpdateCheckResult {
        /// A newer version is available. `storeURL` opens directly to the App Store listing.
        case updateRequired(storeVersion: String, storeURL: URL)
        /// The installed version is current.
        case upToDate
        /// The check could not be completed (no network, app not listed yet, etc.).
        /// The app should continue to load normally in this case.
        case unavailable
    }

    // MARK: - Public API

    /// Fetches the latest version from the App Store and compares it to the
    /// currently installed version. Always calls `completion` on the **main thread**.
    func checkForUpdate(completion: @escaping (UpdateCheckResult) -> Void) {
        guard let url = lookupURL() else {
            DispatchQueue.main.async { completion(.unavailable) }
            return
        }

        let task = URLSession.shared.dataTask(with: url) { [weak self] data, response, _ in
            guard let self = self,
                  let data = data,
                  let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let results = json["results"] as? [[String: Any]],
                  let first = results.first,
                  let storeVersionString = first["version"] as? String,
                  let trackURLString = first["trackViewUrl"] as? String,
                  let storeURL = URL(string: trackURLString)
            else {
                DispatchQueue.main.async { completion(.unavailable) }
                return
            }

            let installedVersion = self.installedVersion()
            let result: UpdateCheckResult

            if self.isVersion(storeVersionString, newerThan: installedVersion) {
                result = .updateRequired(storeVersion: storeVersionString, storeURL: storeURL)
            } else {
                result = .upToDate
            }

            DispatchQueue.main.async { completion(result) }
        }
        task.resume()
    }

    // MARK: - Helpers

    private func lookupURL() -> URL? {
        var components = URLComponents(string: "https://itunes.apple.com/lookup")
        components?.queryItems = [
            URLQueryItem(name: "bundleId", value: bundleID),
            // Bust the CDN cache so we always get the most recent data.
            URLQueryItem(name: "t", value: String(Int(Date().timeIntervalSince1970)))
        ]
        return components?.url
    }

    /// Returns the CFBundleShortVersionString (marketing version, e.g. "2.1.0") of
    /// the running app, or "0.0.0" as a safe fallback.
    private func installedVersion() -> String {
        Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "0.0.0"
    }

    /// Compares two semantic-version strings component-by-component.
    /// Returns `true` only when `candidate` is strictly greater than `installed`.
    /// Non-numeric components are treated as 0 so pre-release labels don't crash.
    private func isVersion(_ candidate: String, newerThan installed: String) -> Bool {
        let candidateParts = candidate.split(separator: ".").map { Int($0) ?? 0 }
        let installedParts = installed.split(separator: ".").map { Int($0) ?? 0 }

        let maxLength = max(candidateParts.count, installedParts.count)
        for i in 0..<maxLength {
            let c = i < candidateParts.count ? candidateParts[i] : 0
            let p = i < installedParts.count ? installedParts[i] : 0
            if c > p { return true }
            if c < p { return false }
        }
        return false // Equal versions
    }
}
