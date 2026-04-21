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
import android.widget.Toast;

import androidx.browser.customtabs.CustomTabColorSchemeParams;
import androidx.browser.customtabs.CustomTabsIntent;
import androidx.core.view.WindowCompat;
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {

    // --- Layout ------------------------------------------------------------------
    private SwipeRefreshLayout swipeRefreshLayout;

    // --- Offline handling --------------------------------------------------------
    private final Handler connectivityHandler = new Handler(Looper.getMainLooper());
    private Runnable connectivityChecker;
    private String  pendingUrl          = null;  // URL blocked due to no internet
    private boolean isShowingOfflinePage = false;

    // The offline page is bundled in the APK assets (via cap sync)
    private static final String OFFLINE_PAGE = "file:///android_asset/public/nointernet.html";
    // The home page Capacitor serves from bundled assets
    private static final String HOME_URL     = "https://localhost/index.html";

    // --- Double back press -------------------------------------------------------
    private long  backPressedTime = 0;
    private Toast backExitToast;

    // =============================================================================
    //  Lifecycle
    // =============================================================================

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // Fit content within status-bar + nav-bar insets (no fullscreen)
        WindowCompat.setDecorFitsSystemWindows(getWindow(), true);

        setupSwipeRefresh();
        setupLinkInterception();
    }

    @Override
    public void onResume() {
        super.onResume();
        WindowCompat.setDecorFitsSystemWindows(getWindow(), true);

        // If the offline page is showing (e.g. user went to Settings to turn on WiFi),
        // resume polling so the app recovers immediately when connectivity returns.
        if (isShowingOfflinePage) {
            WebView wv = getBridge().getWebView();
            if (wv != null) startConnectivityPolling(wv);
        }
    }

    @Override
    public void onPause() {
        super.onPause();
        stopConnectivityPolling(); // battery-friendly: stop polling in background
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) WindowCompat.setDecorFitsSystemWindows(getWindow(), true);
    }

    // =============================================================================
    //  Swipe-to-Refresh (pure native, no JS/HTML dependency)
    // =============================================================================

    private void setupSwipeRefresh() {
        swipeRefreshLayout = findViewById(R.id.swipeRefreshLayout);
        if (swipeRefreshLayout == null) return;

        swipeRefreshLayout.setColorSchemeColors(
            Color.parseColor("#482dff"),
            Color.parseColor("#6c52ff"),
            Color.parseColor("#8a79ff")
        );

        swipeRefreshLayout.setOnRefreshListener(() -> {
            WebView wv = getBridge().getWebView();
            if (wv == null) { swipeRefreshLayout.setRefreshing(false); return; }

            // If offline, don't try to reload — show offline page instead
            if (!isConnected()) {
                swipeRefreshLayout.setRefreshing(false);
                showOfflinePage(wv, wv.getUrl());
                return;
            }

            // Temporarily override client to catch onPageFinished, then restore
            WebViewClient saved = wv.getWebViewClient();
            wv.setWebViewClient(new WebViewClient() {
                @Override
                public void onPageFinished(WebView view, String url) {
                    super.onPageFinished(view, url);
                    view.setWebViewClient(saved);
                    view.post(() -> swipeRefreshLayout.setRefreshing(false));
                }
            });
            wv.reload();

            // Safety net: hide spinner after 8 s even if onPageFinished never fires
            new Handler(getMainLooper()).postDelayed(() -> {
                if (swipeRefreshLayout.isRefreshing()) swipeRefreshLayout.setRefreshing(false);
            }, 8000);
        });

        // Only allow pull when the WebView is scrolled to the very top
        WebView wv = getBridge().getWebView();
        if (wv != null) {
            wv.getViewTreeObserver().addOnScrollChangedListener(() -> {
                if (swipeRefreshLayout != null)
                    swipeRefreshLayout.setEnabled(wv.getScrollY() == 0);
            });
        }
    }

    // =============================================================================
    //  Link Interception + Offline Handling
    // =============================================================================

    private void setupLinkInterception() {
        WebView wv = getBridge().getWebView();
        if (wv == null) return;

        WebViewClient capClient = wv.getWebViewClient();

        wv.setWebViewClient(new WebViewClient() {

            // ------------------------------------------------------------------
            //  URL routing
            // ------------------------------------------------------------------
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                String url = request.getUrl().toString();

                if (isBundledUrl(url)) {
                    // Capacitor's local assets — works offline, let it load
                    return capClient.shouldOverrideUrlLoading(view, request);
                }

                if (isOwnSiteUrl(url)) {
                    // Remote pages on findjobsinfinland.fi — need internet
                    if (!isConnected()) {
                        showOfflinePage(view, url);
                        return true;
                    }
                    return capClient.shouldOverrideUrlLoading(view, request);
                }

                // Everything else → Chrome Custom Tab (in-app browser)
                openInCustomTab(url);
                return true;
            }

            // ------------------------------------------------------------------
            //  Error handling — catches failed main-frame loads (e.g. offline)
            // ------------------------------------------------------------------
            @Override
            public void onReceivedError(WebView view, WebResourceRequest request,
                                        WebResourceError error) {
                if (!request.isForMainFrame()) {
                    // Sub-resource errors (images, fonts…) — let Capacitor decide
                    capClient.onReceivedError(view, request, error);
                    return;
                }

                String failedUrl = request.getUrl().toString();

                // IMPORTANT: Never intercept errors from Capacitor's own local server
                // (https://localhost). If localhost fails it's a build/asset issue,
                // not a connectivity problem, and intercepting it would cause an
                // infinite loop: localhost fails → show offline page → poll → reload
                // localhost → fails again → repeat forever.
                if (isBundledUrl(failedUrl)) {
                    capClient.onReceivedError(view, request, error);
                    return;
                }

                // Already showing offline page — don't re-trigger
                if (isShowingOfflinePage) return;

                int code = error.getErrorCode();
                boolean isNetworkError = (code == WebViewClient.ERROR_IO
                    || code == WebViewClient.ERROR_HOST_LOOKUP
                    || code == WebViewClient.ERROR_CONNECT
                    || code == WebViewClient.ERROR_TIMEOUT
                    || code == WebViewClient.ERROR_FAILED_SSL_HANDSHAKE);

                if (isNetworkError || !isConnected()) {
                    showOfflinePage(view, failedUrl);
                } else {
                    capClient.onReceivedError(view, request, error);
                }
            }

            // Delegate the rest to Capacitor's client so routing/splash still works
            @Override public void onPageStarted(WebView v, String url, Bitmap fav) { capClient.onPageStarted(v, url, fav); }
            @Override public void onPageFinished(WebView v, String url) { capClient.onPageFinished(v, url); }
            @Override public void onReceivedHttpError(WebView v, WebResourceRequest req, WebResourceResponse resp) { capClient.onReceivedHttpError(v, req, resp); }
            @Override public void onReceivedSslError(WebView v, SslErrorHandler h, SslError err) { capClient.onReceivedSslError(v, h, err); }
        });
    }

    // =============================================================================
    //  Offline page + connectivity recovery
    // =============================================================================

    private void showOfflinePage(WebView wv, String blockedUrl) {
        isShowingOfflinePage = true;
        // Only track remote URLs as pending (localhost failures can't be recovered
        // by connectivity polling — they're asset-bundling issues, not network issues)
        if (blockedUrl != null && isOwnSiteUrl(blockedUrl)) {
            pendingUrl = blockedUrl;
        } else {
            pendingUrl = null; // nothing to reload
        }

        stopConnectivityPolling();
        wv.stopLoading();
        wv.post(() -> {
            wv.loadUrl(OFFLINE_PAGE);
            // Clear history after the offline page loads so pressing Back exits the
            // app instead of going back to the error page
            new Handler(Looper.getMainLooper()).postDelayed(() -> {
                if (isShowingOfflinePage) wv.clearHistory();
            }, 400);
        });
        startConnectivityPolling(wv);
    }

    /** Polls every 1 second; when connectivity returns, reloads the pending URL. */
    private void startConnectivityPolling(WebView wv) {
        stopConnectivityPolling();
        connectivityChecker = new Runnable() {
            @Override public void run() {
                if (isConnected()) {
                    stopConnectivityPolling();
                    isShowingOfflinePage = false;
                    // Only reload a remote URL that was blocked; if there's no
                    // pending URL (e.g. localhost failed), do nothing — the user
                    // can pull-to-refresh or navigate manually.
                    if (pendingUrl != null) {
                        String target = pendingUrl;
                        pendingUrl = null;
                        wv.post(() -> wv.loadUrl(target));
                    } else {
                        // Just mark as recovered; the nointernet.html "Retry" button
                        // or pull-to-refresh will complete the navigation.
                        wv.post(() -> wv.loadUrl(HOME_URL));
                    }
                } else {
                    connectivityHandler.postDelayed(this, 1000);
                }
            }
        };
        connectivityHandler.postDelayed(connectivityChecker, 1000);
    }

    private void stopConnectivityPolling() {
        if (connectivityChecker != null) {
            connectivityHandler.removeCallbacks(connectivityChecker);
            connectivityChecker = null;
        }
    }

    private boolean isConnected() {
        ConnectivityManager cm = (ConnectivityManager) getSystemService(Context.CONNECTIVITY_SERVICE);
        if (cm == null) return false;
        android.net.Network net = cm.getActiveNetwork();
        if (net == null) return false;
        NetworkCapabilities caps = cm.getNetworkCapabilities(net);
        return caps != null && (
            caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)     ||
            caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) ||
            caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET)
        );
    }

    // =============================================================================
    //  Double back press to exit
    // =============================================================================

    @Override
    @SuppressWarnings("deprecation")        // onBackPressed is still the right hook for BridgeActivity subclasses
    public void onBackPressed() {
        if (getBridge() == null) {
            // Bridge not ready — fall back to system behavior
            super.onBackPressed();
            return;
        }
        WebView wv = getBridge().getWebView();

        // Let the WebView navigate back normally (Jobs → Home, etc.)
        // BUT skip this when the offline page is showing — its history entries
        // point to broken error pages, so going back would just show errors again.
        if (!isShowingOfflinePage && wv != null && wv.canGoBack()) {
            wv.goBack();
            return;
        }

        // On root screen: require a second press within 2 s to exit
        long now = System.currentTimeMillis();
        if (now - backPressedTime < 2000) {
            if (backExitToast != null) backExitToast.cancel();
            finishAffinity();   // closes the app reliably on all Android versions
        } else {
            backPressedTime = now;
            if (backExitToast != null) backExitToast.cancel();
            backExitToast = Toast.makeText(
                this, "Press back again to exit", Toast.LENGTH_SHORT);
            backExitToast.show();
        }
    }

    // =============================================================================
    //  Helpers
    // =============================================================================

    /** Bundled assets served by Capacitor's local server — work offline. */
    private boolean isBundledUrl(String url) {
        return url.startsWith("http://localhost")
            || url.startsWith("https://localhost")
            || url.startsWith("capacitor://")
            || url.startsWith("android-app://")
            || url.startsWith("file:///android_asset/");
    }

    /** Remote pages on the own website — need internet. */
    private boolean isOwnSiteUrl(String url) {
        return url.startsWith("https://findjobsinfinland.fi/")
            || url.startsWith("http://findjobsinfinland.fi/");
    }

    /** Opens an external URL in a branded Chrome Custom Tab (in-app browser). */
    private void openInCustomTab(String url) {
        try {
            CustomTabColorSchemeParams colors = new CustomTabColorSchemeParams.Builder()
                .setToolbarColor(Color.parseColor("#482dff"))
                .build();
            new CustomTabsIntent.Builder()
                .setShowTitle(true)
                .setDefaultColorSchemeParams(colors)
                .build()
                .launchUrl(this, Uri.parse(url));
        } catch (Exception e) {
            try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url))); }
            catch (Exception ignored) { }
        }
    }
}
