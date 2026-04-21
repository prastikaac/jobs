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
        // Call the web-side refresh handler
        webView?.evaluateJavaScript(
            "if(window.AppPullToRefresh) window.AppPullToRefresh.onRefresh();",
            completionHandler: nil
        )

        // Listen for completion via JS event
        listenForRefreshComplete()
    }

    private func listenForRefreshComplete() {
        // Inject a one-shot listener that sets a flag when refresh completes
        webView?.evaluateJavaScript(
            "document._appRefreshDone = false;" +
            "document.addEventListener('app:refreshComplete', function() {" +
            "  document._appRefreshDone = true;" +
            "}, {once: true});",
            completionHandler: nil
        )

        pollRefreshDone(startTime: Date())
    }

    private func pollRefreshDone(startTime: Date) {
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { [weak self] in
            guard let self = self else { return }

            let elapsed = Date().timeIntervalSince(startTime)
            if elapsed >= 8.0 {
                // Timeout — stop spinner regardless
                self.refreshControl.endRefreshing()
                return
            }

            self.webView?.evaluateJavaScript("document._appRefreshDone === true ? 'done' : 'waiting'") { result, _ in
                if let val = result as? String, val == "done" {
                    DispatchQueue.main.async {
                        self.refreshControl.endRefreshing()
                    }
                } else {
                    self.pollRefreshDone(startTime: startTime)
                }
            }
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
