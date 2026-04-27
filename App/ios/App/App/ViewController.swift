import UIKit
import Capacitor
import WebKit
import SafariServices

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
        setupLinkInterception()
        applySafeAreaInsets()
    }

    /// Forces the WKWebView scroll view to always respect iOS safe area insets.
    /// This prevents content from scrolling under the status bar (top)
    /// and the home indicator / tab bar (bottom) — even while scrolling.
    private func applySafeAreaInsets() {
        webView?.scrollView.contentInsetAdjustmentBehavior = .always
    }

    override func viewDidLayoutSubviews() {
        super.viewDidLayoutSubviews()
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

    // MARK: - External Link Interception
    private var capNavigationDelegate: WKNavigationDelegate?

    private func setupLinkInterception() {
        // Save the original Capacitor delegate and set ourselves as the delegate
        self.capNavigationDelegate = self.webView?.navigationDelegate
        self.webView?.navigationDelegate = self
    }

    deinit {
        NotificationCenter.default.removeObserver(self)
    }
}

// Forward WKNavigationDelegate calls to Capacitor, but intercept external links
extension ViewController: WKNavigationDelegate {
    
    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        if let url = navigationAction.request.url {
            let urlString = url.absoluteString
            let isOwnSite = urlString.hasPrefix("https://findjobsinfinland.fi/") || urlString.hasPrefix("http://findjobsinfinland.fi/")
            let isBundled = urlString.hasPrefix("capacitor://") || urlString.hasPrefix("http://localhost") || urlString.hasPrefix("https://localhost")
            
            if !isOwnSite && !isBundled && (urlString.hasPrefix("http://") || urlString.hasPrefix("https://")) {
                // External link — open in in-app Safari browser
                decisionHandler(.cancel)
                
                let safariVC = SFSafariViewController(url: url)
                safariVC.preferredControlTintColor = UIColor(red: 0.282, green: 0.176, blue: 1.0, alpha: 1.0)
                self.present(safariVC, animated: true, completion: nil)
                return
            }
        }
        
        if let capDelegate = capNavigationDelegate, capDelegate.responds(to: #selector(webView(_:decidePolicyFor:decisionHandler:))) {
            capDelegate.webView?(webView, decidePolicyFor: navigationAction, decisionHandler: decisionHandler)
        } else {
            decisionHandler(.allow)
        }
    }
    
    func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) {
        capNavigationDelegate?.webView?(webView, didStartProvisionalNavigation: navigation)
    }
    
    func webView(_ webView: WKWebView, didReceiveServerRedirectForProvisionalNavigation navigation: WKNavigation!) {
        capNavigationDelegate?.webView?(webView, didReceiveServerRedirectForProvisionalNavigation: navigation)
    }
    
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        capNavigationDelegate?.webView?(webView, didFailProvisionalNavigation: navigation, withError: error)
    }
    
    func webView(_ webView: WKWebView, didCommit navigation: WKNavigation!) {
        capNavigationDelegate?.webView?(webView, didCommit: navigation)
    }
    
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        capNavigationDelegate?.webView?(webView, didFinish: navigation)
        // Hide splash screen explicitly when the live website finishes loading
        webView.evaluateJavaScript("if (window.Capacitor && window.Capacitor.Plugins.SplashScreen) { window.Capacitor.Plugins.SplashScreen.hide(); }", completionHandler: nil)
    }
    
    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        capNavigationDelegate?.webView?(webView, didFail: navigation, withError: error)
    }
    
    func webView(_ webView: WKWebView, didReceive challenge: URLAuthenticationChallenge, completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void) {
        if let capDelegate = capNavigationDelegate, capDelegate.responds(to: #selector(webView(_:didReceive:completionHandler:))) {
            capDelegate.webView?(webView, didReceive: challenge, completionHandler: completionHandler)
        } else {
            completionHandler(.performDefaultHandling, nil)
        }
    }
    
    @available(iOS 14.5, *)
    func webView(_ webView: WKWebView, navigationAction: WKNavigationAction, didBecome download: WKDownload) {
        if let capDelegate = capNavigationDelegate, capDelegate.responds(to: #selector(webView(_:navigationAction:didBecome:))) {
            capDelegate.webView?(webView, navigationAction: navigationAction, didBecome: download)
        }
    }
    
    @available(iOS 14.5, *)
    func webView(_ webView: WKWebView, navigationResponse: WKNavigationResponse, didBecome download: WKDownload) {
        if let capDelegate = capNavigationDelegate, capDelegate.responds(to: #selector(webView(_:navigationResponse:didBecome:))) {
            capDelegate.webView?(webView, navigationResponse: navigationResponse, didBecome: download)
        }
    }
    
    func webView(_ webView: WKWebView, decidePolicyFor navigationResponse: WKNavigationResponse, decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void) {
        if let capDelegate = capNavigationDelegate, capDelegate.responds(to: #selector(webView(_:decidePolicyFor:decisionHandler:) as ((WKWebView, WKNavigationResponse, @escaping (WKNavigationResponsePolicy) -> Void) -> Void)?)) {
            capDelegate.webView?(webView, decidePolicyFor: navigationResponse, decisionHandler: decisionHandler)
        } else {
            decisionHandler(.allow)
        }
    }
}
