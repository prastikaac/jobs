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

        view.backgroundColor = UIColor(red: 0.07, green: 0.07, blue: 0.07, alpha: 1.0)

        webView?.isOpaque = false
        webView?.backgroundColor = UIColor.clear
        webView?.scrollView.backgroundColor = UIColor.clear
        webView?.allowsBackForwardNavigationGestures = true

        setupAppResumeObserver()
    }

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)

        setupPullToRefresh()
        setupWebViewDelegates()
        injectExternalLinkHandler()
    }

    // MARK: - Native iOS Pull To Refresh

    private func setupPullToRefresh() {
        guard let scrollView = webView?.scrollView else { return }

        if refreshControl != nil { return }

        refreshControl = UIRefreshControl()
        refreshControl.tintColor = UIColor(red: 0.282, green: 0.176, blue: 1.0, alpha: 1.0)
        refreshControl.addTarget(self, action: #selector(handleRefresh), for: .valueChanged)

        scrollView.refreshControl = refreshControl
        scrollView.bounces = true
    }

    /// Called when the user pulls down and releases.
    /// Tries the JS-side smart refresh first; falls back to a full WebKit reload
    /// only if the JS bridge is not available (e.g. error page, JS not loaded yet).
    @objc private func handleRefresh() {
        guard let webView = webView else {
            refreshControl?.endRefreshing()
            return
        }

        // Register a one-shot message handler BEFORE calling JS so the
        // "done" signal from the JS side can be received.
        let controller = webView.configuration.userContentController
        controller.removeScriptMessageHandler(forName: "refreshComplete")
        controller.add(self, name: "refreshComplete")

        // Patch signalDone in the JS layer so it also posts back to native,
        // then kick off the smart refresh. Returns true if JS handled it,
        // false if the bridge isn't available (triggers native full reload).
        let js = """
        (function() {
            if (window.AppPullToRefresh && typeof window.AppPullToRefresh.onRefresh === 'function') {
                var _orig = window.AppPullToRefresh.signalDone;
                window.AppPullToRefresh.signalDone = function() {
                    if (_orig) _orig();
                    window.webkit.messageHandlers.refreshComplete.postMessage('done');
                };
                window.AppPullToRefresh.onRefresh();
                return true;
            }
            return false;
        })();
        """

        webView.evaluateJavaScript(js) { [weak self] result, _ in
            guard let self = self else { return }
            let jsHandled = (result as? Bool) == true
            if !jsHandled {
                // JS bridge not ready — full WebKit reload; spinner ends in didFinish/didFail
                webView.reload()
            }
            // else: waiting for "refreshComplete" message or navigation didFinish
        }

        // Safety timeout: stop spinner if neither JS nor navigation finishes within 15 s
        DispatchQueue.main.asyncAfter(deadline: .now() + 15) { [weak self] in
            guard let self = self, self.refreshControl?.isRefreshing == true else { return }
            self.finishRefreshing()
        }
    }

    /// Stops the pull-to-refresh spinner and removes the one-shot message handler.
    private func finishRefreshing() {
        DispatchQueue.main.async { [weak self] in
            guard let self = self else { return }
            self.refreshControl?.endRefreshing()
            self.webView?.configuration.userContentController
                .removeScriptMessageHandler(forName: "refreshComplete")
        }
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

    // MARK: - Browser Opening

    private func openBuiltInBrowser(_ url: URL) {
        DispatchQueue.main.async { [weak self] in
            guard let self = self else { return }
            if self.presentedViewController is SFSafariViewController { return }
            let safariVC = SFSafariViewController(url: url)
            safariVC.preferredControlTintColor = UIColor(red: 0.282, green: 0.176, blue: 1.0, alpha: 1.0)
            safariVC.modalPresentationStyle = .fullScreen
            self.present(safariVC, animated: false)
        }
    }

    private func openSystemApp(_ url: URL) {
        DispatchQueue.main.async {
            UIApplication.shared.open(url, options: [:], completionHandler: nil)
        }
    }

    // MARK: - JavaScript External Link Handler

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

            function isExternalUrl(href) {
                try {
                    var url = new URL(href, window.location.href);
                    var host = url.hostname.toLowerCase();
                    var isHttp = url.protocol === 'http:' || url.protocol === 'https:';
                    var isOwnSite =
                        host === 'findjobsinfinland.fi' ||
                        host === 'www.findjobsinfinland.fi';
                    return isHttp && !isOwnSite;
                } catch(e) {
                    return false;
                }
            }

            function openExternal(href) {
                try {
                    var url = new URL(href, window.location.href);
                    window.webkit.messageHandlers.externalLink.postMessage(url.href);
                } catch(e) {}
            }

            document.addEventListener('click', function(event) {
                var anchor = findAnchor(event.target);
                if (!anchor || !anchor.href) return;
                if (isExternalUrl(anchor.href)) {
                    event.preventDefault();
                    event.stopImmediatePropagation();
                    event.stopPropagation();
                    openExternal(anchor.href);
                    return false;
                }
            }, true);

            var originalOpen = window.open;
            window.open = function(url) {
                if (isExternalUrl(url)) {
                    openExternal(url);
                    return null;
                }
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
        webView?.configuration.userContentController.removeScriptMessageHandler(forName: "refreshComplete")
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

        if shouldOpenInBuiltInBrowser(url) {
            decisionHandler(.cancel)
            openBuiltInBrowser(url)
            return
        }

        if scheme == "mailto" || scheme == "tel" || scheme == "sms" {
            decisionHandler(.cancel)
            openSystemApp(url)
            return
        }

        decisionHandler(.allow)
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        originalNavigationDelegate?.webView?(webView, didFinish: navigation)
        injectExternalLinkHandler()
        webView.evaluateJavaScript(
            "if (window.Capacitor && window.Capacitor.Plugins.SplashScreen) { window.Capacitor.Plugins.SplashScreen.hide(); }",
            completionHandler: nil
        )
        // Covers the full-reload path (JS bridge wasn't ready)
        finishRefreshing()
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        originalNavigationDelegate?.webView?(webView, didFail: navigation, withError: error)
        finishRefreshing()
    }

    func webView(_ webView: WKWebView,
                 didFailProvisionalNavigation navigation: WKNavigation!,
                 withError error: Error) {
        originalNavigationDelegate?.webView?(webView, didFailProvisionalNavigation: navigation, withError: error)
        finishRefreshing()
    }
}

// MARK: - WKUIDelegate

extension ViewController: WKUIDelegate {

    func webView(_ webView: WKWebView,
                 createWebViewWith configuration: WKWebViewConfiguration,
                 for navigationAction: WKNavigationAction,
                 windowFeatures: WKWindowFeatures) -> WKWebView? {

        guard let url = navigationAction.request.url else { return nil }

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
        switch message.name {

        case "externalLink":
            guard let urlString = message.body as? String,
                  let url = URL(string: urlString) else { return }
            if shouldOpenInBuiltInBrowser(url) {
                openBuiltInBrowser(url)
            }

        case "refreshComplete":
            // JS smart refresh finished — hide the native spinner
            finishRefreshing()

        default:
            break
        }
    }
}