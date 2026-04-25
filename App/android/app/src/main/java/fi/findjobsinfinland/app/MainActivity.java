package fi.findjobsinfinland.app;

import android.content.Context;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.net.ConnectivityManager;
import android.net.NetworkCapabilities;
import android.net.Uri;
import android.net.http.SslError;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.webkit.SslErrorHandler;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import java.io.InputStream;
import android.widget.Toast;

import androidx.browser.customtabs.CustomTabColorSchemeParams;
import androidx.browser.customtabs.CustomTabsIntent;
import androidx.core.view.WindowCompat;
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout;

import com.getcapacitor.BridgeActivity;
import com.getcapacitor.WebViewListener;

public class MainActivity extends BridgeActivity {

    // --- Layout ------------------------------------------------------------------
    private SwipeRefreshLayout swipeRefreshLayout;

    // --- Offline recovery --------------------------------------------------------
    // Tracks the last real page URL natively so the no-internet page can return
    // to it. We can't use sessionStorage because the error page is served from
    // the localhost origin while normal pages are on findjobsinfinland.fi.
    private String lastVisitedUrl = "https://findjobsinfinland.fi/";

    // --- Error page tracking -----------------------------------------------------
    // URL-based detection is unreliable because loadDataWithBaseURL uses
    // historyUrl="https://findjobsinfinland.fi/" — so wv.getUrl() returns the
    // site root, not a path containing "error.html". A boolean flag is the only
    // reliable way to know we're currently showing an error/offline page.
    private boolean isOnErrorPage = false;

    // Tracks the last page that SUCCESSFULLY loaded (no error). Used by the back
    // button on the error page as a guaranteed fallback when the WebView history
    // has no usable entry (e.g. error on first page load, or all history entries
    // are error/failed-URL entries).
    private String lastSuccessfulUrl = "https://findjobsinfinland.fi/";

    // --- Double back press -------------------------------------------------------
    private long  backPressedTime = 0;
    private Toast backExitToast;

    // --- Network Poller ----------------------------------------------------------
    private android.os.Handler networkPollHandler = new android.os.Handler(android.os.Looper.getMainLooper());
    private Runnable networkPollRunnable = new Runnable() {
        @Override
        public void run() {
            if (getBridge() != null && getBridge().getWebView() != null) {
                WebView wv = getBridge().getWebView();
                String currentUrl = wv.getUrl();
                // Detect when we're on the offline page (loadDataWithBaseURL sets URL to the base URL)
                boolean onOfflinePage = (currentUrl == null)
                    || currentUrl.contains("nointernet.html")
                    || currentUrl.equals("file:///android_asset/public/");
                if (onOfflinePage && isConnected()) {
                    // Silent ping to confirm real connectivity before restoring page
                    new Thread(() -> {
                        try {
                            java.net.HttpURLConnection conn = (java.net.HttpURLConnection)
                                new java.net.URL("https://findjobsinfinland.fi/images/icon.png").openConnection();
                            conn.setRequestMethod("HEAD");
                            conn.setConnectTimeout(2000);
                            conn.setReadTimeout(2000);
                            if (conn.getResponseCode() == 200) {
                                wv.post(() -> wv.loadUrl(lastVisitedUrl));
                            }
                        } catch (Exception e) { /* still offline */ }
                    }).start();
                }
            }
            networkPollHandler.postDelayed(this, 3000);
        }
    };

    // =============================================================================
    //  Lifecycle
    // =============================================================================

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        WindowCompat.setDecorFitsSystemWindows(getWindow(), true);
    }

    @Override
    public void onResume() {
        super.onResume();
        WindowCompat.setDecorFitsSystemWindows(getWindow(), true);
    }

    @Override
    public void onPause() {
        super.onPause();
        // Force Android to write cookies to disk immediately when the app goes to background
        android.webkit.CookieManager.getInstance().flush();
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) WindowCompat.setDecorFitsSystemWindows(getWindow(), true);
    }

    // Capacitor allows us to inject JS on page load securely via WebViewListener
    @Override
    public void onStart() {
        super.onStart();
        
        // Enforce cookie acceptance and persistence
        android.webkit.CookieManager cookieManager = android.webkit.CookieManager.getInstance();
        cookieManager.setAcceptCookie(true);
        if (getBridge() != null && getBridge().getWebView() != null) {
            cookieManager.setAcceptThirdPartyCookies(getBridge().getWebView(), true);
            
            // Enforce DOM storage (localStorage) which most cookie banners use
            getBridge().getWebView().getSettings().setDomStorageEnabled(true);
            getBridge().getWebView().getSettings().setDatabaseEnabled(true);
            
            // If the app is launched offline, bypass the 10-second WebView timeout
            // and immediately load the offline page.
            if (!isConnected()) {
                getBridge().getWebView().post(() -> {
                    loadAssetPage(getBridge().getWebView(), "nointernet.html");
                });
            }

            // Start the 3-second network polling loop natively
            networkPollHandler.post(networkPollRunnable);
        }

        // Inject custom WebViewClient to route network errors and HTTP errors differently
        if (getBridge() != null && getBridge().getWebView() != null) {
            getBridge().getWebView().setWebViewClient(new com.getcapacitor.BridgeWebViewClient(getBridge()) {

                // ── PRE-FLIGHT CHECK ────────────────────────────────────────────────────
                // Intercept BEFORE the request is even sent. If we already know we have
                // no connection, load the offline page immediately — the browser error
                // screen is never shown because the request is cancelled right here.
                @Override
                public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                    String url = request.getUrl().toString();
                    // Only gate on real HTTP(S) navigations for the main frame.
                    // Allow file:// and localhost URLs through unconditionally.
                    if (request.isForMainFrame()
                            && (url.startsWith("https://") || url.startsWith("http://"))
                            && !url.contains("nointernet.html")
                            && !url.contains("error.html")) {
                        if (!isConnected()) {
                            // Track where the user was trying to go
                            lastVisitedUrl = url;
                            // Cancel the navigation and show offline page instantly.
                            // loadAssetPage inlines the HTML — no file:// URL needed.
                            view.post(() -> loadAssetPage(view, "nointernet.html"));
                            return true; // We handled it — WebView must NOT proceed
                        }
                    }
                    // Let Capacitor/WebView handle all other navigations normally
                    return super.shouldOverrideUrlLoading(view, request);
                }

                // ── FALLBACK: catches errors that slip past the pre-flight ───────────
                // (e.g. connection drops mid-request, or DNS failures)
                @Override
                public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                    // Do NOT call super — calling super lets Chromium render its own error page.
                    if (request.isForMainFrame()) {
                        String failedUrl = request.getUrl().toString();
                        // Don't update lastVisitedUrl for our own error pages
                        if (!failedUrl.contains("nointernet.html") && !failedUrl.contains("error.html")) {
                            lastVisitedUrl = failedUrl;
                        } else {
                            // An asset page itself failed — skip (don't loop)
                            return;
                        }

                        // stopLoading() prevents Chromium from finishing its error render.
                        // loadAssetPage() inlines HTML directly — no file:// URL lookup.
                        view.stopLoading();
                        view.post(() -> {
                            if (!isConnected()) {
                                loadAssetPage(view, "nointernet.html");
                            } else {
                                loadAssetPage(view, "error.html");
                            }
                        });
                    }
                }

                @Override
                public void onReceivedHttpError(WebView view, WebResourceRequest request, WebResourceResponse errorResponse) {
                    // Do NOT call super — calling super lets Capacitor/Chromium process
                    // the HTTP error first (render a blank/error page), which races against
                    // our loadAssetPage call and causes a blank white screen.
                    if (request.isForMainFrame()) {
                        String failedUrl = request.getUrl().toString();
                        if (!failedUrl.contains("nointernet.html") && !failedUrl.contains("error.html")) {
                            lastVisitedUrl = failedUrl;
                            view.stopLoading();
                            view.post(() -> loadAssetPage(view, "error.html"));
                        }
                    }
                }

                @Override
                public void onReceivedSslError(WebView view, SslErrorHandler handler, android.net.http.SslError error) {
                    // Cancel the SSL handshake. onReceivedError will fire next and
                    // handle the redirect — no need to call loadAssetPage here too.
                    handler.cancel();
                }
            });
        }

        int nightModeFlags = getResources().getConfiguration().uiMode & android.content.res.Configuration.UI_MODE_NIGHT_MASK;
        if (nightModeFlags == android.content.res.Configuration.UI_MODE_NIGHT_YES) {
            getBridge().getWebView().setBackgroundColor(Color.parseColor("#121212"));
        } else {
            getBridge().getWebView().setBackgroundColor(Color.parseColor("#ffffff"));
        }

        getBridge().getWebView().addJavascriptInterface(new Object() {
            @android.webkit.JavascriptInterface
            public void openSocialLink(String url) {
                Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
                String pkg = null;
                if (url.contains("linkedin.com")) pkg = "com.linkedin.android";
                else if (url.contains("facebook.com")) pkg = "com.facebook.katana";
                else if (url.contains("instagram.com")) pkg = "com.instagram.android";
                
                if (pkg != null) {
                    intent.setPackage(pkg);
                }
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);

                try {
                    MainActivity.this.startActivity(intent);
                } catch (Exception e) {
                    Intent fallback = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
                    fallback.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                    try {
                        MainActivity.this.startActivity(fallback);
                    } catch (Exception ex) {
                        // ignore
                    }
                }
            }
        }, "SocialAppOpener");

        // Expose a native bridge so the no-internet page can trigger a real
        // page load from native code (bypasses Capacitor's error-path loop).
        getBridge().getWebView().addJavascriptInterface(new Object() {
            @android.webkit.JavascriptInterface
            public String getLastUrl() {
                return lastVisitedUrl;
            }

            @android.webkit.JavascriptInterface
            public void reloadPage(String url) {
                final String target = (url != null && !url.isEmpty()) ? url : lastVisitedUrl;
                runOnUiThread(() -> {
                    WebView wv = getBridge().getWebView();
                    if (wv != null) {
                        wv.loadUrl(target);
                    }
                });
            }
        }, "PageReloader");

        setupSwipeRefresh();

        getBridge().addWebViewListener(new WebViewListener() {
            @Override
            public void onPageLoaded(WebView webView) {
                // Hide splash instantly as soon as the page is loaded.
                webView.evaluateJavascript(
                    "if (window.Capacitor && window.Capacitor.Plugins.SplashScreen) {" +
                    "  window.Capacitor.Plugins.SplashScreen.hide({ fadeOutDuration: 0 });" +
                    "}",
                    null
                );

                // Hide swipe-to-refresh spinner
                if (swipeRefreshLayout != null && swipeRefreshLayout.isRefreshing()) {
                    swipeRefreshLayout.post(() -> swipeRefreshLayout.setRefreshing(false));
                }

                // Inject JS to handle external links via Capacitor Browser plugin.
                // NOTE: We deliberately do NOT check navigator.onLine here for internal
                // links. That API is unreliable on Android and causes false-positive
                // offline redirects. Instead, we let the WebView naturally attempt the
                // navigation; if the network is truly down, Capacitor's errorPath
                // ("nointernet.html") will kick in automatically.
                String js = "document.removeEventListener('click', window._capLinkInterceptor, true);" +
                            "window._capLinkInterceptor = function(e) {" +
                            "  var a = e.target.closest('a');" +
                            "  if (a && a.href && a.href.startsWith('http')) {" +
                            "    var isInternal = a.href.indexOf('findjobsinfinland.fi') !== -1 || a.href.indexOf('localhost') !== -1;" +
                            "    if (!isInternal) {" +
                            "      e.preventDefault();" +
                            "      var u = a.href.toLowerCase();" +
                            "      var isSocial = u.includes('linkedin.com') || u.includes('facebook.com') || u.includes('instagram.com');" +
                            "      if (isSocial && window.SocialAppOpener) {" +
                            "        window.SocialAppOpener.openSocialLink(a.href);" +
                            "      } else if (window.Capacitor && window.Capacitor.Plugins.Browser) {" +
                            "        window.Capacitor.Plugins.Browser.open({ url: a.href, presentationStyle: 'fullscreen' });" +
                            "      } else {" +
                            "        window.open(a.href, '_blank');" +
                            "      }" +
                            "    }" +
                            "  }" +
                            "};" +
                            "document.addEventListener('click', window._capLinkInterceptor, true);" +
                            // Continuously track the current page URL so the offline
                            // page knows where to return when connectivity resumes.
                            "try { sessionStorage.setItem('app_last_page_before_offline', window.location.href); } catch(_) {}";

                // Also track it natively (sessionStorage is origin-scoped and
                // won't be readable from the localhost-served error page).
                // Guard with isOnErrorPage: when the error page fires onPageLoaded,
                // wv.getUrl() returns "https://findjobsinfinland.fi/" (our historyUrl)
                // which would wrongly overwrite the real lastVisitedUrl.
                if (!isOnErrorPage) {
                    String currentUrl = webView.getUrl();
                    if (currentUrl != null
                            && !currentUrl.isEmpty()
                            && !currentUrl.contains("nointernet.html")
                            && !currentUrl.contains("error.html")) {
                        lastVisitedUrl = currentUrl;
                        // Also update the "last successful" tracker used by the
                        // back button on the error page as a guaranteed fallback.
                        lastSuccessfulUrl = currentUrl;
                    }
                }
                webView.evaluateJavascript(js, null);
            }
        });
    }

    // =============================================================================
    //  Swipe-to-Refresh (pure native, no JS/HTML dependency)
    // =============================================================================

    private void setupSwipeRefresh() {
        WebView wv = getBridge().getWebView();
        if (wv == null) return;

        // Dynamically wrap WebView if not already wrapped
        if (wv.getParent() instanceof SwipeRefreshLayout) {
            swipeRefreshLayout = (SwipeRefreshLayout) wv.getParent();
        } else {
            swipeRefreshLayout = new SwipeRefreshLayout(this);
            android.view.ViewGroup parent = (android.view.ViewGroup) wv.getParent();
            if (parent != null) {
                parent.removeView(wv);
                swipeRefreshLayout.addView(wv, new android.view.ViewGroup.LayoutParams(
                    android.view.ViewGroup.LayoutParams.MATCH_PARENT, 
                    android.view.ViewGroup.LayoutParams.MATCH_PARENT
                ));
                parent.addView(swipeRefreshLayout, new android.view.ViewGroup.LayoutParams(
                    android.view.ViewGroup.LayoutParams.MATCH_PARENT, 
                    android.view.ViewGroup.LayoutParams.MATCH_PARENT
                ));
            } else {
                return; // Not attached yet
            }
        }

        // Match the SwipeRefreshLayout background and arrow color to the current theme
        // so it looks natural and doesn't flash a contrasting colour.
        int nightModeFlags = getResources().getConfiguration().uiMode
                & android.content.res.Configuration.UI_MODE_NIGHT_MASK;
        if (nightModeFlags == android.content.res.Configuration.UI_MODE_NIGHT_YES) {
            swipeRefreshLayout.setProgressBackgroundColorSchemeColor(Color.parseColor("#121212"));
            swipeRefreshLayout.setColorSchemeColors(Color.parseColor("#ffffff")); // White arrow for dark mode
        } else {
            swipeRefreshLayout.setProgressBackgroundColorSchemeColor(Color.parseColor("#ffffff"));
            swipeRefreshLayout.setColorSchemeColors(Color.parseColor("#000000")); // Black arrow for light mode
        }

        swipeRefreshLayout.setOnRefreshListener(() -> {
            if (!isConnected()) {
                swipeRefreshLayout.setRefreshing(false);
                loadAssetPage(wv, "nointernet.html");
                return;
            }

            if (isOnErrorPage) {
                // The WebView URL is the asset base URL, not a real HTTP address.
                // Calling wv.loadUrl(currentUrl) would load an empty directory
                // and show a blank screen.  Instead, reload the last successful page
                // (with a background ping first to avoid showing error.html again
                // if the target is still broken).
                if (lastSuccessfulUrl != null && !lastSuccessfulUrl.isEmpty()) {
                    new Thread(() -> {
                        try {
                            java.net.HttpURLConnection conn = (java.net.HttpURLConnection)
                                new java.net.URL(lastSuccessfulUrl).openConnection();
                            conn.setRequestMethod("HEAD");
                            conn.setConnectTimeout(3000);
                            conn.setReadTimeout(3000);
                            int code = conn.getResponseCode();
                            if (code >= 200 && code < 400) {
                                wv.post(() -> {
                                    isOnErrorPage = false;
                                    wv.loadUrl(lastSuccessfulUrl);
                                });
                            } else {
                                // Target still broken — re-show error page (no blank flash)
                                wv.post(() -> {
                                    swipeRefreshLayout.setRefreshing(false);
                                    loadAssetPage(wv, "error.html");
                                });
                            }
                        } catch (Exception e) {
                            wv.post(() -> {
                                swipeRefreshLayout.setRefreshing(false);
                                if (!isConnected()) loadAssetPage(wv, "nointernet.html");
                                else loadAssetPage(wv, "error.html");
                            });
                        }
                    }).start();
                } else {
                    // No previous URL to return to — just re-show error page cleanly
                    swipeRefreshLayout.setRefreshing(false);
                    loadAssetPage(wv, "error.html");
                }
            } else {
                String currentUrl = wv.getUrl();
                if (currentUrl != null && !currentUrl.isEmpty()) {
                    wv.loadUrl(currentUrl);
                } else {
                    swipeRefreshLayout.setRefreshing(false);
                }
            }

            // Safety net: hide spinner after 8 s even if onPageFinished never fires
            new Handler(getMainLooper()).postDelayed(() -> {
                if (swipeRefreshLayout != null && swipeRefreshLayout.isRefreshing()) {
                    swipeRefreshLayout.setRefreshing(false);
                }
            }, 8000);
        });

        // Only allow pull when the WebView is scrolled to the very top
        wv.getViewTreeObserver().addOnScrollChangedListener(() -> {
            if (swipeRefreshLayout != null) {
                boolean shouldEnable = (wv.getScrollY() == 0);
                if (swipeRefreshLayout.isEnabled() != shouldEnable) {
                    swipeRefreshLayout.setEnabled(shouldEnable);
                }
            }
        });
    }

    // =============================================================================
    //  Helpers
    // =============================================================================

    private boolean isConnected() {
        try {
            ConnectivityManager cm = (ConnectivityManager) getSystemService(Context.CONNECTIVITY_SERVICE);
            if (cm == null) return true;
            android.net.Network net = cm.getActiveNetwork();
            if (net == null) return false;
            NetworkCapabilities caps = cm.getNetworkCapabilities(net);
            return caps != null && (
                caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)     ||
                caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) ||
                caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET)
            );
        } catch (Exception e) {
            return true; // Safety net: assume connected if permission is denied or missing to avoid breaking app
        }
    }

    /**
     * Load an error/offline page by reading its HTML directly from Android assets
     * and injecting it via loadDataWithBaseURL. This completely avoids file:// URL
     * resolution, which is what caused ERR_FILE_NOT_FOUND in the WebView.
     *
     * @param view      The WebView to load into
     * @param filename  Filename inside assets/public/, e.g. "nointernet.html"
     */
    private void loadAssetPage(WebView view, String filename) {
        // Mark that we are now showing an error/offline asset page.
        // onBackPressed and onPageLoaded both rely on this flag because
        // URL-based detection no longer works (historyUrl = site root).
        isOnErrorPage = true;
        try {
            InputStream is = getAssets().open("public/" + filename);
            java.io.ByteArrayOutputStream baos = new java.io.ByteArrayOutputStream();
            byte[] buffer = new byte[1024];
            int length;
            while ((length = is.read(buffer)) != -1) {
                baos.write(buffer, 0, length);
            }
            is.close();
            String html = baos.toString("UTF-8");
            // baseUrl = file:// so relative asset paths (images, css, js) resolve.
            // historyUrl = the site origin so the WebView's back-stack entry is a
            // real URL (not null / file://) which prevents blank-screen on reload
            // and keeps Capacitor's origin checks happy.
            view.loadDataWithBaseURL(
                "file:///android_asset/public/",
                html,
                "text/html",
                "UTF-8",
                "https://findjobsinfinland.fi/"
            );
        } catch (Exception e) {
            // Absolute last-resort fallback: plain message with no white flash
            view.loadData(
                "<html><body style='display:flex;align-items:center;justify-content:center;" +
                "height:100vh;font-family:sans-serif;font-size:18px;color:#555;'>" +
                "<p>Something went wrong. Please go back and try again.</p> <script src="/js/main.js"></script>
</body></html>",
                "text/html", "UTF-8"
            );
        }
    }

    // =============================================================================
    //  Double back press to exit
    // =============================================================================

    @Override
    @SuppressWarnings("deprecation")        // onBackPressed is still the right hook for BridgeActivity subclasses
    public void onBackPressed() {
        if (getBridge() == null) {
            super.onBackPressed();
            return;
        }
        WebView wv = getBridge().getWebView();



        if (wv != null) {
            // Use the flag instead of URL checks — wv.getUrl() returns the site
            // root (our historyUrl) when on the error page, not "error.html".
            if (isOnErrorPage) {
                // Walk history backwards, skipping:
                //  • error/offline asset entries (file:// base URL)
                //  • the URL that triggered the error (lastVisitedUrl) — going
                //    back to it would just show the error page again.
                android.webkit.WebBackForwardList list = wv.copyBackForwardList();
                int currentIndex = list.getCurrentIndex();
                int stepsToSkip = 0;

                for (int i = currentIndex; i >= 0; i--) {
                    String url = list.getItemAtIndex(i).getUrl();
                    boolean shouldSkip = url == null
                            || url.equals("file:///android_asset/public/")
                            || url.contains("nointernet.html")
                            || url.contains("error.html")
                            // Skip the historyUrl we injected for the error page
                            || (url.equals("https://findjobsinfinland.fi/") && i == currentIndex)
                            // Skip the failed URL — reloading it would error again
                            || url.equals(lastVisitedUrl);
                    if (shouldSkip) {
                        stepsToSkip++;
                    } else {
                        break;
                    }
                }

                isOnErrorPage = false;
                if (stepsToSkip > 0 && wv.canGoBackOrForward(-stepsToSkip)) {
                    // Found a valid history entry — navigate there.
                    wv.goBackOrForward(-stepsToSkip);
                } else {
                    // No usable history entry (e.g. error on very first load).
                    // Fall back to the last page that actually loaded successfully
                    // rather than showing the exit toast.
                    wv.loadUrl(lastSuccessfulUrl);
                }
                return;
            } else if (wv.canGoBack()) {
                wv.goBack();
                return;
            }
        }

        // Root screen: require a second press within 2 s to exit
        long now = System.currentTimeMillis();
        if (now - backPressedTime < 2000) {
            if (backExitToast != null) backExitToast.cancel();
            finishAffinity();
        } else {
            backPressedTime = now;
            if (backExitToast != null) backExitToast.cancel();
            backExitToast = Toast.makeText(
                this, "Press back again to exit", Toast.LENGTH_SHORT);
            backExitToast.show();
        }
    }
}
