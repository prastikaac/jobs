import UIKit
import Capacitor
import WebKit

/// Main view controller — subclasses CAPBridgeViewController to add:
///   - Pull-to-refresh via UIRefreshControl on WKWebView.scrollView
///   - Native back/forward swipe gestures
///   - App resume → silent data refresh
class ViewController: CAPBridgeViewController {

    private var refreshControl: UIRefreshControl!

    // MARK: - Lifecycle

    override func viewDidLoad() {
        super.viewDidLoad()
        setupPullToRefresh()
        setupSwipeGestures()
        setupAppResumeObserver()
    }

    // MARK: - Pull-to-Refresh

    private func setupPullToRefresh() {
        refreshControl = UIRefreshControl()

        // Brand color: #482dff
        refreshControl.tintColor = UIColor(red: 0.282, green: 0.176, blue: 1.0, alpha: 1.0)

        refreshControl.addTarget(self, action: #selector(handleRefresh), for: .valueChanged)

        // Attach to WKWebView's scroll view (the correct iOS approach)
        webView?.scrollView.addSubview(refreshControl)
        webView?.scrollView.bounces = true
    }

    @objc private func handleRefresh() {
        webView?.reload()
        
        // Stop spinner after a reasonable time since page load will finish
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) { [weak self] in
            self?.refreshControl.endRefreshing()
        }
    }

    // MARK: - Swipe Gestures (iOS native back/forward)

    private func setupSwipeGestures() {
        // Enable WKWebView's built-in back/forward swipe navigation
        webView?.allowsBackForwardNavigationGestures = true
    }

    // MARK: - App Resume (silent refresh)

    private func setupAppResumeObserver() {
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(appDidBecomeActive),
            name: UIApplication.didBecomeActiveNotification,
            object: nil
        )
    }

    @objc private func appDidBecomeActive() {
        // Trigger silent data refresh on web side — don't reload the page
        webView?.evaluateJavaScript(
            "if(window.AppData && window.AppData.silentRefresh) window.AppData.silentRefresh();",
            completionHandler: nil
        )
    }

    deinit {
        NotificationCenter.default.removeObserver(self)
    }
}
