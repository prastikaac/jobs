import UIKit
import Capacitor
import WebKit
import SafariServices

/// Main view controller — subclasses CAPBridgeViewController to add:
///   - Pull-to-refresh via UIRefreshControl on WKWebView.scrollView
///   - Native back/forward swipe gestures
///   - App resume → silent data refresh
///   - External links open in an in-app browser instead of device Safari
class ViewController: CAPBridgeViewController {

    private var refreshControl: UIRefreshControl!
    private var capNavigationDelegate: WKNavigationDelegate?

    // MARK: - Lifecycle

    override func viewDidLoad() {
        super.viewDidLoad()

        edgesForExtendedLayout = []
        extendedLayoutIncludesOpaqueBars = false

        webView?.isOpaque = false
        updateBackgroundColor()

        setupSwipeGestures()
        setupAppResumeObserver()
        setupLinkInterception()
    }

    override func traitCollectionDidChange(_ previousTraitCollection: UITraitCollection?) {
        super.traitCollectionDidChange(previousTraitCollection)
        updateBackgroundColor()
    }

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        setupPullToRefresh()
    }

    private func updateBackgroundColor() {
        if traitCollection.userInterfaceStyle == .dark {
            webView?.backgroundColor = UIColor(red: 0.07, green: 0.07, blue: 0.07, alpha: 1.0)
            view.backgroundColor = UIColor(red: 0.07, green: 0.07, blue: 0.07, alpha: 1.0)
        } else {
            webView?.backgroundColor = .white
            view.backgroundColor = .white
        }
    }

    // MARK: - Pull-to-Refresh

    private func setupPullToRefresh() {
        guard let scrollView = webView?.scrollView else { return }

        if refreshControl != nil { return }

        refreshControl = UIRefreshControl()
        refreshControl.tintColor = UIColor(red: 0.282, green: 0.176, blue: 1.0, alpha: 1.0)
        refreshControl.addTarget(self, action: #selector(handleRefresh), for: .valueChanged)

        scrollView.addSubview(refreshControl)
        scrollView.bounces = true
    }

    @objc private func handleRefresh() {
        webView?.reload()
    }

    // MARK: - Swipe Gestures

    private func setupSwipeGestures() {
        webView?.allowsBackForwardNavigationGestures = true
    }

    // MARK: - App Resume

    private func setupAppResumeObserver() {
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(appDidBecomeActive),
            name: UIApplication.didBecomeActiveNotification,
            object: nil
        )
    }

    @objc private func appDidBecomeActive() {
        webView?.evaluateJavaScript(
            "if(window.AppData && window.AppData.silentRefresh) window.AppData.silentRefresh();",
            completionHandler: nil
        )
    }

    // MARK: - External Link Interception

    private func setupLinkInterception() {
        // Keep Capacitor's original delegate and forward events to it.
        capNavigationDelegate = webView?.navigationDelegate

        // navigationDelegate handles normal link clicks.
        webView?.navigationDelegate = self

        // uiDelegate handles target="_blank" and window.open() links.
        // This is the usual reason external links still open in device Safari.
        webView?.uiDelegate = self
    }

    private func isFindJobsInFinlandURL(_ url: URL) -> Bool {
        guard let host = url.host?.lowercased() else { return false }
        return host == "findjobsinfinland.fi" || host == "www.findjobsinfinland.fi"
    }

    private func isBundledOrLocalURL(_ url: URL) -> Bool {
        let scheme = url.scheme?.lowercased() ?? ""
        let host = url.host?.lowercased() ?? ""

        return scheme == "capacitor" || host == "localhost" || host == "127.0.0.1"
    }

    private func shouldOpenInInAppBrowser(_ url: URL) -> Bool {
        let scheme = url.scheme?.lowercased() ?? ""
        guard scheme == "http" || scheme == "https" else { return false }

        // Keep only your own website in the main WebView.
        // Everything else opens in built-in in-app browser mode.
        return !isFindJobsInFinlandURL(url) && !isBundledOrLocalURL(url)
    }

    private func openInAppBrowser(_ url: URL) {
        let safariVC = SFSafariViewController(url: url)
        safariVC.preferredControlTintColor = UIColor(red: 0.282, green: 0.176, blue: 1.0, alpha: 1.0)
        safariVC.modalPresentationStyle = .fullScreen
        present(safariVC, animated: true, completion: nil)
    }

    deinit {
        NotificationCenter.default.removeObserver(self)
    }
}

// MARK: - WKNavigationDelegate

extension ViewController: WKNavigationDelegate {

    func webView(_ webView: WKWebView,
                 decidePolicyFor navigationAction: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        if let url = navigationAction.request.url, shouldOpenInInAppBrowser(url) {
            decisionHandler(.cancel)
            openInAppBrowser(url)
            return
        }

        if let capDelegate = capNavigationDelegate,
           capDelegate.responds(to: #selector(webView(_:decidePolicyFor:decisionHandler:))) {
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
        webView.evaluateJavaScript("if (window.Capacitor && window.Capacitor.Plugins.SplashScreen) { window.Capacitor.Plugins.SplashScreen.hide(); }", completionHandler: nil)
        DispatchQueue.main.async { [weak self] in
            self?.refreshControl?.endRefreshing()
        }
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        capNavigationDelegate?.webView?(webView, didFail: navigation, withError: error)
        DispatchQueue.main.async { [weak self] in
            self?.refreshControl?.endRefreshing()
        }
    }

    func webView(_ webView: WKWebView,
                 didReceive challenge: URLAuthenticationChallenge,
                 completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void) {
        if let capDelegate = capNavigationDelegate,
           capDelegate.responds(to: #selector(webView(_:didReceive:completionHandler:))) {
            capDelegate.webView?(webView, didReceive: challenge, completionHandler: completionHandler)
        } else {
            completionHandler(.performDefaultHandling, nil)
        }
    }

    @available(iOS 14.5, *)
    func webView(_ webView: WKWebView, navigationAction: WKNavigationAction, didBecome download: WKDownload) {
        if let capDelegate = capNavigationDelegate,
           capDelegate.responds(to: #selector(webView(_:navigationAction:didBecome:))) {
            capDelegate.webView?(webView, navigationAction: navigationAction, didBecome: download)
        }
    }

    @available(iOS 14.5, *)
    func webView(_ webView: WKWebView, navigationResponse: WKNavigationResponse, didBecome download: WKDownload) {
        if let capDelegate = capNavigationDelegate,
           capDelegate.responds(to: #selector(webView(_:navigationResponse:didBecome:))) {
            capDelegate.webView?(webView, navigationResponse: navigationResponse, didBecome: download)
        }
    }

    func webView(_ webView: WKWebView,
                 decidePolicyFor navigationResponse: WKNavigationResponse,
                 decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void) {
        if let capDelegate = capNavigationDelegate,
           capDelegate.responds(to: #selector(webView(_:decidePolicyFor:decisionHandler:) as ((WKWebView, WKNavigationResponse, @escaping (WKNavigationResponsePolicy) -> Void) -> Void)?)) {
            capDelegate.webView?(webView, decidePolicyFor: navigationResponse, decisionHandler: decisionHandler)
        } else {
            decisionHandler(.allow)
        }
    }
}

// MARK: - WKUIDelegate

extension ViewController: WKUIDelegate {

    func webView(_ webView: WKWebView,
                 createWebViewWith configuration: WKWebViewConfiguration,
                 for navigationAction: WKNavigationAction,
                 windowFeatures: WKWindowFeatures) -> WKWebView? {

        guard let url = navigationAction.request.url else { return nil }

        if shouldOpenInInAppBrowser(url) {
            openInAppBrowser(url)
            return nil
        }

        // Same-domain target="_blank" links should stay inside the main WebView.
        if isFindJobsInFinlandURL(url) || isBundledOrLocalURL(url) {
            webView.load(navigationAction.request)
            return nil
        }

        return nil
    }
}
