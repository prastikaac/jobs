import UIKit
import WebKit
import SafariServices

class ViewController: UIViewController {

    // MARK: - Properties

    private var webView: WKWebView!
    private var refreshControl: UIRefreshControl!
    private var splashOverlayView: UIView?
    private let mainDomain = "findjobsinfinland.fi"
    private let startURL = URL(string: "https://findjobsinfinland.fi/")!

    // MARK: - Lifecycle

    override func viewDidLoad() {
        super.viewDidLoad()
        
        // Define a dynamic color that perfectly matches the website's header/footer backgrounds
        // Dark mode: #121212 (0.07, 0.07, 0.07). Light mode: White.
        let adaptiveBgColor = UIColor { traitCollection in
            return traitCollection.userInterfaceStyle == .dark
                ? UIColor(red: 0.07, green: 0.07, blue: 0.07, alpha: 1.0)
                : .white
        }
        
        view.backgroundColor = adaptiveBgColor
        setupWebView()
        setupSplashOverlay()      // Show splash overlay over the empty webview
        setupWebViewDelegates()   // must be set BEFORE load()
        setupAppResumeObserver()
        webView.load(URLRequest(url: startURL))
    }

    // MARK: - Splash Screen Overlay

    private func setupSplashOverlay() {
        let overlay = UIView(frame: view.bounds)
        overlay.backgroundColor = view.backgroundColor
        overlay.autoresizingMask = [.flexibleWidth, .flexibleHeight]

        let imageView = UIImageView(image: UIImage(named: "Splash"))
        imageView.contentMode = .scaleAspectFit
        imageView.translatesAutoresizingMaskIntoConstraints = false
        overlay.addSubview(imageView)

        NSLayoutConstraint.activate([
            imageView.centerXAnchor.constraint(equalTo: overlay.centerXAnchor),
            imageView.centerYAnchor.constraint(equalTo: overlay.centerYAnchor),
            imageView.widthAnchor.constraint(equalToConstant: 160),
            imageView.heightAnchor.constraint(equalToConstant: 160)
        ])

        view.addSubview(overlay)
        splashOverlayView = overlay
    }

    private func hideSplashOverlay() {
        guard let overlay = splashOverlayView else { return }
        splashOverlayView = nil

        UIView.animate(withDuration: 0.4, delay: 0.1, options: .curveEaseInOut, animations: {
            overlay.alpha = 0
            overlay.transform = CGAffineTransform(scaleX: 1.05, y: 1.05)
        }) { _ in
            overlay.removeFromSuperview()
        }
    }

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        setupPullToRefresh()
        injectExternalLinkHandler()
    }

    // MARK: - WKWebView Setup

    private func setupWebView() {
        let config = WKWebViewConfiguration()
        config.allowsInlineMediaPlayback = true
        config.mediaTypesRequiringUserActionForPlayback = []

        // Disable pinch-to-zoom by injecting a viewport override at document load.
        // Works even when the page already has a <meta name="viewport"> tag.
        let noZoomJS = #"""
        (function() {
            var meta = document.querySelector('meta[name="viewport"]');
            if (meta) {
                // Strip any existing user-scalable / scale limits, then add ours
                var c = meta.content
                    .replace(/user-scalable\s*=\s*[^,]+/gi, '')
                    .replace(/minimum-scale\s*=\s*[^,]+/gi, '')
                    .replace(/maximum-scale\s*=\s*[^,]+/gi, '')
                    .replace(/,\s*,/g, ',')
                    .replace(/(^,|,$)/g, '')
                    .trim();
                meta.content = c + ', user-scalable=no, minimum-scale=1.0, maximum-scale=1.0';
            } else {
                var m = document.createElement('meta');
                m.name = 'viewport';
                m.content = 'width=device-width, initial-scale=1.0, user-scalable=no';
                document.head.appendChild(m);
            }
        })();
        """#
        let noZoomScript = WKUserScript(
            source: noZoomJS,
            injectionTime: .atDocumentEnd,
            forMainFrameOnly: true
        )
        config.userContentController.addUserScript(noZoomScript)

        webView = WKWebView(frame: .zero, configuration: config)
        webView.translatesAutoresizingMaskIntoConstraints = false
        // isOpaque must stay TRUE — setting it to false causes a black screen
        // while WKWebView's compositor initialises. Let the webpage set its own bg.
        // Make background adaptive so overscrolling and safe areas match the website header/footer perfectly.
        webView.underPageBackgroundColor = view.backgroundColor
        webView.backgroundColor = view.backgroundColor
        webView.scrollView.backgroundColor = view.backgroundColor
        webView.allowsBackForwardNavigationGestures = true
        webView.customUserAgent = "FindJobsFinlandApp/1.0 (iOS)"

        // Belt-and-suspenders: also lock the scroll view zoom so UIKit
        // doesn't allow a pinch gesture to scale the web view at all.
        webView.scrollView.minimumZoomScale = 1.0
        webView.scrollView.maximumZoomScale = 1.0
        webView.scrollView.bouncesZoom = false

        view.addSubview(webView)

        NSLayoutConstraint.activate([
            webView.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor),
            webView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            webView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            webView.bottomAnchor.constraint(equalTo: view.safeAreaLayoutGuide.bottomAnchor),
        ])
    }

    // MARK: - Native iOS Pull To Refresh

    private func setupPullToRefresh() {
        guard refreshControl == nil else { return }

        refreshControl = UIRefreshControl()
        // .label automatically switches to black in light mode, white in dark mode
        refreshControl.tintColor = .label
        refreshControl.addTarget(self, action: #selector(handleRefresh), for: .valueChanged)

        webView.scrollView.refreshControl = refreshControl
        webView.scrollView.bounces = true
    }

    /// Called when the user pulls down and releases.
    /// Tries the JS-side smart refresh first; falls back to a full WebKit reload
    /// only if the JS bridge is not available (e.g. error page, JS not loaded yet).
    @objc private func handleRefresh() {
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
                self.webView.reload()
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
            self.webView.configuration.userContentController
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
        webView.evaluateJavaScript(
            "if(window.AppData && window.AppData.silentRefresh) window.AppData.silentRefresh();",
            completionHandler: nil
        )
    }

    // MARK: - WebView Delegates

    private func setupWebViewDelegates() {
        webView.navigationDelegate = self
        webView.uiDelegate = self
    }

    // MARK: - URL Rules

    private func isMainDomain(_ url: URL) -> Bool {
        guard let host = url.host?.lowercased() else { return false }
        return host == mainDomain || host == "www.\(mainDomain)"
    }

    private func isLocalAppUrl(_ url: URL) -> Bool {
        let host = url.host?.lowercased() ?? ""
        return host == "localhost" || host == "127.0.0.1"
    }

    private func isHttpUrl(_ url: URL) -> Bool {
        let scheme = url.scheme?.lowercased() ?? ""
        return scheme == "http" || scheme == "https"
    }

    private func isSocialAppUrl(_ url: URL) -> Bool {
        guard let host = url.host?.lowercased() else { return false }
        return host.contains("facebook.com") ||
               host.contains("instagram.com") ||
               host.contains("twitter.com") ||
               host.contains("x.com") ||
               host.contains("linkedin.com")
    }

    private func shouldOpenInBuiltInBrowser(_ url: URL) -> Bool {
        if !isHttpUrl(url) { return false }
        if isLocalAppUrl(url) { return false }
        if isMainDomain(url) { return false }
        if isSocialAppUrl(url) { return false }
        return true
    }

    // MARK: - Browser Opening

    private func openBuiltInBrowser(_ url: URL) {
        DispatchQueue.main.async { [weak self] in
            guard let self = self else { return }
            if self.presentedViewController is SFSafariViewController { return }
            let safariVC = SFSafariViewController(url: url)
            // UIColor.label = black in light mode, white in dark mode — matches system appearance
            safariVC.preferredControlTintColor = UIColor.label
            safariVC.modalPresentationStyle = .fullScreen
            self.present(safariVC, animated: false)
        }
    }

    private func openSystemApp(_ url: URL) {
        DispatchQueue.main.async {
            UIApplication.shared.open(url, options: [:], completionHandler: nil)
        }
    }

    private func openSocialAppOrBrowser(_ url: URL) {
        DispatchQueue.main.async { [weak self] in
            // Try to open using universal links (native app)
            UIApplication.shared.open(url, options: [.universalLinksOnly: true]) { success in
                if !success {
                    // Fall back to built-in browser if the native app isn't installed
                    self?.openBuiltInBrowser(url)
                }
            }
        }
    }

    // MARK: - JavaScript External Link Handler

    private func injectExternalLinkHandler() {
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

            // Track whether we are inside a real user click gesture.
            // This prevents programmatic window.open() calls (ads, analytics)
            // from being intercepted as if the user tapped an external link.
            var _inUserClick = false;

            document.addEventListener('click', function(event) {
                _inUserClick = true;
                // Reset after current call-stack unwinds
                setTimeout(function() { _inUserClick = false; }, 300);

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
                // Only intercept window.open() that originated from a user tap,
                // NOT auto-called scripts that run on page load.
                if (_inUserClick && isExternalUrl(url)) {
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

        if scheme == "mailto" || scheme == "tel" || scheme == "sms" {
            decisionHandler(.cancel)
            openSystemApp(url)
            return
        }

        // Only open external links in the built-in browser for MAIN-FRAME navigations.
        // Sub-frame navigations (iframes, embedded widgets, ad networks) must be
        // allowed through; intercepting them is what caused rogue popups on page load.
        let isMainFrame = navigationAction.targetFrame?.isMainFrame ?? false
        if isMainFrame {
            if isSocialAppUrl(url) {
                decisionHandler(.cancel)
                openSocialAppOrBrowser(url)
                return
            }
            if shouldOpenInBuiltInBrowser(url) {
                decisionHandler(.cancel)
                openBuiltInBrowser(url)
                return
            }
        }

        decisionHandler(.allow)
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        hideSplashOverlay()
        injectExternalLinkHandler()
        finishRefreshing()
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        hideSplashOverlay()
        finishRefreshing()
    }

    func webView(_ webView: WKWebView,
                 didFailProvisionalNavigation navigation: WKNavigation!,
                 withError error: Error) {
        hideSplashOverlay()
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

        if isSocialAppUrl(url) {
            openSocialAppOrBrowser(url)
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
        switch message.name {

        case "externalLink":
            guard let urlString = message.body as? String,
                  let url = URL(string: urlString) else { return }
            if isSocialAppUrl(url) {
                openSocialAppOrBrowser(url)
            } else if shouldOpenInBuiltInBrowser(url) {
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