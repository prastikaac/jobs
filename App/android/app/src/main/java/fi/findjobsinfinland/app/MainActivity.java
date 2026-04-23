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
                    super.onReceivedHttpError(view, request, errorResponse);
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
                String currentUrl = webView.getUrl();
                if (currentUrl != null
                        && !currentUrl.isEmpty()
                        && !currentUrl.contains("nointernet.html")
                        && !currentUrl.contains("error.html")) {
                    lastVisitedUrl = currentUrl;
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

            // Grab the current URL and navigate to it fresh from the server.
            // This keeps the old page painted until the new one is ready (no
            // white flash) and is a genuine network fetch, not a cache hit.
            String currentUrl = wv.getUrl();
            boolean onErrorPage = currentUrl == null
                || currentUrl.equals("file:///android_asset/public/")
                || currentUrl.contains("nointernet.html")
                || currentUrl.contains("error.html");

            if (onErrorPage) {
                if (lastVisitedUrl != null && !lastVisitedUrl.isEmpty()) {
                    wv.loadUrl(lastVisitedUrl);
                } else {
                    swipeRefreshLayout.setRefreshing(false);
                }
            } else if (currentUrl != null && !currentUrl.isEmpty()) {
                wv.loadUrl(currentUrl);
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
        try {
            InputStream is = getAssets().open("public/" + filename);
            byte[] buffer = new byte[is.available()];
            //noinspection ResultOfMethodCallIgnored
            is.read(buffer);
            is.close();
            String html = new String(buffer, "UTF-8");
            // Use a file:// base URL so relative asset paths still resolve correctly
            view.loadDataWithBaseURL(
                "file:///android_asset/public/",
                html,
                "text/html",
                "UTF-8",
                null
            );
        } catch (Exception e) {
            // Absolute last-resort fallback: blank white page with a plain message
            view.loadData(
                "<html><body style='display:flex;align-items:center;justify-content:center;" +
                "height:100vh;font-family:sans-serif;font-size:18px;color:#555;'>" +
                "<p>No Internet Connection</p></body></html>",
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

        // Detect whether we are currently showing an error/offline page.
        // loadDataWithBaseURL sets getUrl() to the base URL we passed in,
        // so we also check for that sentinel value.
        String currentUrl = (wv != null) ? wv.getUrl() : null;
        boolean onErrorPage = currentUrl == null
                || currentUrl.equals("file:///android_asset/public/")
                || currentUrl.contains("nointernet.html")
                || currentUrl.contains("error.html");

        if (onErrorPage) {
            // We are on an error page. Don't call wv.goBack() — that would just
            // navigate back into the failed URL and re-trigger the same error.
            // Instead: if the site is reachable load lastVisitedUrl, otherwise
            // treat this as the root screen (double-press to exit).
            if (isConnected() && lastVisitedUrl != null && !lastVisitedUrl.isEmpty()) {
                wv.loadUrl(lastVisitedUrl);
            } else {
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
            return;
        }

        // Normal page — let the WebView navigate back through its history
        if (wv != null && wv.canGoBack()) {
            wv.goBack();
            return;
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
