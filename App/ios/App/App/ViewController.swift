import UIKit
import Capacitor
import WebKit
import SafariServices

class ViewController: CAPBridgeViewController {

    private var refreshControl: UIRefreshControl!
    private var originalNavigationDelegate: WKNavigationDelegate?

    private let mainDomain = "findjobsinfinland.fi"

    override func viewDidLoad() {
        super.viewDidLoad()

        edgesForExtendedLayout = []
        extendedLayoutIncludesOpaqueBars = false

        webView?.isOpaque = false
        updateBackgroundColor()

        setupSwipeGestures()
        setupAppResumeObserver()
    }

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)

        setupPullToRefresh()

        // Important: Capacitor may set delegates after viewDidLoad,
        // so set our delegates again here.
        setupWebViewDelegates()
        injectExternalLinkHandler()
    }

    override func traitCollectionDidChange(_ previousTraitCollection: UITraitCollection?) {
        super.traitCollectionDidChange(previousTraitCollection)
        updateBackgroundColor()
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

    // MARK: - Pull To Refresh

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

    // MARK: - Swipe Gesture

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

    // MARK: - WebView Delegates

    private func setupWebViewDelegates() {
        if originalNavigationDelegate == nil,
           let currentDelegate = webView?.navigationDelegate,
           !(currentDelegate === self) {
            originalNavigationDelegate = currentDelegate
        }

        webView?.navigationDelegate = self
        webView?.uiDelegate = self
    }

    // MARK: - URL Rules

    private func isMainDomain(_ url: URL) -> Bool {
        guard let host = url.host?.lowercased() else { return false }

        return host == mainDomain || host == "www.\(mainDomain)"
    }

    private func isLocalAppUrl(_ url: URL) -> Bool {
        let scheme = url.scheme?.lowercased() ?? ""
        let host = url.host?.lowercased() ?? ""

        return scheme == "capacitor"
            || scheme == "ionic"
            || host == "localhost"
            || host == "127.0.0.1"
    }

    private func isHttpUrl(_ url: URL) -> Bool {
        let scheme = url.scheme?.lowercased() ?? ""
        return scheme == "http" || scheme == "https"
    }

    private func shouldOpenInBuiltInBrowser(_ url: URL) -> Bool {
        if !isHttpUrl(url) { return false }
        if isLocalAppUrl(url) { return false }
        if isMainDomain(url) { return false }

        return true
    }

    private func openBuiltInBrowser(_ url: URL) {
        DispatchQueue.main.async { [weak self] in
            guard let self = self else { return }

            let safariVC = SFSafariViewController(url: url)
            safariVC.preferredControlTintColor = UIColor(red: 0.282, green: 0.176, blue: 1.0, alpha: 1.0)
            safariVC.modalPresentationStyle = .fullScreen

            self.present(safariVC, animated: true)
        }
    }

    private func openSystemApp(_ url: URL) {
        DispatchQueue.main.async {
            UIApplication.shared.open(url, options: [:], completionHandler: nil)
        }
    }

    // MARK: - JavaScript Link Handler

    private func injectExternalLinkHandler() {
        guard let webView = webView else { return }

        let js = """
        (function() {
            if (window.__externalLinkHandlerInstalled) return;
            window.__externalLinkHandlerInstalled = true;

            function findAnchor(element) {
                while (element && element.tagName !== 'A') {
                    element = element.parentElement;
                }
                return element;
            }

            document.addEventListener('click', function(event) {
                var anchor = findAnchor(event.target);
                if (!anchor || !anchor.href) return;

                try {
                    var url = new URL(anchor.href);
                    var host = url.hostname.toLowerCase();

                    var isHttp = url.protocol === 'http:' || url.protocol === 'https:';
                    var isOwnSite =
                        host === 'findjobsinfinland.fi' ||
                        host === 'www.findjobsinfinland.fi';

                    if (isHttp && !isOwnSite) {
                        event.preventDefault();
                        event.stopPropagation();
                        window.webkit.messageHandlers.externalLink.postMessage(anchor.href);
                    }
                } catch(e) {}
            }, true);

            var originalOpen = window.open;
            window.open = function(url) {
                try {
                    var parsed = new URL(url, window.location.href);
                    var host = parsed.hostname.toLowerCase();

                    var isHttp = parsed.protocol === 'http:' || parsed.protocol === 'https:';
                    var isOwnSite =
                        host === 'findjobsinfinland.fi' ||
                        host === 'www.findjobsinfinland.fi';

                    if (isHttp && !isOwnSite) {
                        window.webkit.messageHandlers.externalLink.postMessage(parsed.href);
                        return null;
                    }
                } catch(e) {}

                return originalOpen.apply(window, arguments);
            };
        })();
        """

        webView.configuration.userContentController.removeScriptMessageHandler(forName: "externalLink")
        webView.configuration.userContentController.add(self, name: "externalLink")

        webView.evaluateJavaScript(js, completionHandler: nil)
    }

    deinit {
        NotificationCenter.default.removeObserver(self)
        webView?.configuration.userContentController.removeScriptMessageHandler(forName: "externalLink")
    }
}

// MARK: - WKNavigationDelegate

extension ViewController: WKNavigationDelegate {

    func webView(_ webView: WKWebView,
                 decidePolicyFor navigationAction: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {

        guard let url = navigationAction.request.url else {
            decisionHandler(.allow)
            return
        }

        let scheme = url.scheme?.lowercased() ?? ""

        // Open external http/https links inside iOS built-in in-app browser.
        if shouldOpenInBuiltInBrowser(url) {
            decisionHandler(.cancel)
            openBuiltInBrowser(url)
            return
        }

        // Handle mail, phone, SMS, maps, etc.
        if scheme == "mailto" || scheme == "tel" || scheme == "sms" {
            decisionHandler(.cancel)
            openSystemApp(url)
            return
        }

        // Allow your own website and Capacitor local app files.
        decisionHandler(.allow)
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        originalNavigationDelegate?.webView?(webView, didFinish: navigation)

        injectExternalLinkHandler()

        webView.evaluateJavaScript(
            "if (window.Capacitor && window.Capacitor.Plugins.SplashScreen) { window.Capacitor.Plugins.SplashScreen.hide(); }",
            completionHandler: nil
        )

        DispatchQueue.main.async { [weak self] in
            self?.refreshControl?.endRefreshing()
        }
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        originalNavigationDelegate?.webView?(webView, didFail: navigation, withError: error)

        DispatchQueue.main.async { [weak self] in
            self?.refreshControl?.endRefreshing()
        }
    }

    func webView(_ webView: WKWebView,
                 didFailProvisionalNavigation navigation: WKNavigation!,
                 withError error: Error) {
        originalNavigationDelegate?.webView?(webView, didFailProvisionalNavigation: navigation, withError: error)

        DispatchQueue.main.async { [weak self] in
            self?.refreshControl?.endRefreshing()
        }
    }
}

// MARK: - WKUIDelegate

extension ViewController: WKUIDelegate {

    func webView(_ webView: WKWebView,
                 createWebViewWith configuration: WKWebViewConfiguration,
                 for navigationAction: WKNavigationAction,
                 windowFeatures: WKWindowFeatures) -> WKWebView? {

        guard let url = navigationAction.request.url else {
            return nil
        }

        if shouldOpenInBuiltInBrowser(url) {
            openBuiltInBrowser(url)
            return nil
        }

        if isMainDomain(url) || isLocalAppUrl(url) {
            webView.load(navigationAction.request)
            return nil
        }

        return nil
    }
}

// MARK: - WKScriptMessageHandler

extension ViewController: WKScriptMessageHandler {

    func userContentController(_ userContentController: WKUserContentController,
                               didReceive message: WKScriptMessage) {

        guard message.name == "externalLink",
              let urlString = message.body as? String,
              let url = URL(string: urlString) else {
            return
        }

        if shouldOpenInBuiltInBrowser(url) {
            openBuiltInBrowser(url)
        }
    }
}