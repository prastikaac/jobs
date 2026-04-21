package fi.findjobsinfinland.app;

import android.content.Intent;
import android.graphics.Bitmap;
import android.net.Uri;
import android.net.http.SslError;
import android.os.Bundle;
import android.os.Handler;
import android.webkit.SslErrorHandler;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.graphics.Color;
import android.widget.Toast;

import androidx.browser.customtabs.CustomTabColorSchemeParams;
import androidx.browser.customtabs.CustomTabsIntent;

import androidx.core.view.WindowCompat;
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {

    private SwipeRefreshLayout swipeRefreshLayout;

    // --- Double back press to exit -----------------------------------------------
    private long backPressedTime = 0;
    private Toast backExitToast;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // --- Fix full-screen / dancing layout ------------------------------------
        // Tell Android to lay out content within system bar insets (status bar +
        // navigation bar). This stops the WebView from extending under the bars
        // and prevents the page from shifting/dancing when soft keyboard appears.
        WindowCompat.setDecorFitsSystemWindows(getWindow(), true);

        swipeRefreshLayout = findViewById(R.id.swipeRefreshLayout);

        if (swipeRefreshLayout != null) {
            // Brand color: #482dff (primary purple of findjobsinfinland.fi)
            swipeRefreshLayout.setColorSchemeColors(
                Color.parseColor("#482dff"),
                Color.parseColor("#6c52ff"),
                Color.parseColor("#8a79ff")
            );

            swipeRefreshLayout.setOnRefreshListener(() -> {
                WebView webView = getBridge().getWebView();
                if (webView == null) {
                    swipeRefreshLayout.setRefreshing(false);
                    return;
                }

                // --- Pure native reload — no JS dependency -----------------------
                // Override WebViewClient just long enough to catch page-finished,
                // then restore Capacitor's own client so routing still works.
                WebViewClient originalClient = webView.getWebViewClient();
                webView.setWebViewClient(new WebViewClient() {
                    @Override
                    public void onPageFinished(WebView view, String url) {
                        super.onPageFinished(view, url);
                        // Restore Capacitor's client immediately
                        view.setWebViewClient(originalClient);
                        // Hide spinner on main thread
                        view.post(() -> swipeRefreshLayout.setRefreshing(false));
                    }
                });

                webView.reload();

                // Safety net: hide spinner after 8s even if onPageFinished never fires
                new Handler(getMainLooper()).postDelayed(() -> {
                    if (swipeRefreshLayout.isRefreshing()) {
                        swipeRefreshLayout.setRefreshing(false);
                    }
                }, 8000);
            });

            // --- Only allow pull-to-refresh when scrolled to top ----------------
            WebView webView = getBridge().getWebView();
            if (webView != null) {
                webView.getViewTreeObserver().addOnScrollChangedListener(() -> {
                    if (swipeRefreshLayout != null) {
                        swipeRefreshLayout.setEnabled(webView.getScrollY() == 0);
                    }
                });
            }
        }

        // --- Intercept links: open external URLs in Chrome Custom Tab -----------
        setupLinkInterception();
    }

    @Override
    public void onResume() {
        super.onResume();
        // Re-apply in case a plugin or lifecycle event resets it
        WindowCompat.setDecorFitsSystemWindows(getWindow(), true);
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) {
            // Re-apply when splash screen dialog dismisses or window regains focus
            WindowCompat.setDecorFitsSystemWindows(getWindow(), true);
        }
    }

    @Override
    public void onBackPressed() {
        WebView webView = getBridge().getWebView();

        // If the WebView has back history, navigate back normally
        // (this handles in-app navigation: jobs page -> home, etc.)
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
            return;
        }

        // No more history — we are on the root/home screen.
        // Implement double-back-press-to-exit.
        long now = System.currentTimeMillis();
        if (now - backPressedTime < 2000) {
            // Second press within 2 seconds: exit the app
            if (backExitToast != null) backExitToast.cancel();
            super.onBackPressed();
        } else {
            // First press: show hint and record timestamp
            backPressedTime = now;
            if (backExitToast != null) backExitToast.cancel();
            backExitToast = Toast.makeText(this, "Press back again to exit", Toast.LENGTH_SHORT);
            backExitToast.show();
        }
    }

    /**
     * Intercepts WebView URL loads:
     *  - https://findjobsinfinland.fi/* and localhost -> handled by Capacitor (in-app)
     *  - Everything else                             -> Chrome Custom Tab (branded in-app browser)
     *
     * Saves Capacitor's original WebViewClient and delegates all methods back to it
     * so splash-screen hiding, routing, SSL handling, etc. keep working normally.
     */
    private void setupLinkInterception() {
        WebView webView = getBridge().getWebView();
        if (webView == null) return;

        WebViewClient capClient = webView.getWebViewClient();

        webView.setWebViewClient(new WebViewClient() {

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                String url = request.getUrl().toString();
                // Internal: let Capacitor route it inside the WebView
                if (isInternalUrl(url)) {
                    return capClient.shouldOverrideUrlLoading(view, request);
                }
                // External: show in Chrome Custom Tab (in-app browser overlay)
                openInCustomTab(url);
                return true;
            }

            // Delegate all Capacitor WebViewClient hooks so nothing breaks
            @Override public void onPageStarted(WebView v, String url, Bitmap favicon) { capClient.onPageStarted(v, url, favicon); }
            @Override public void onPageFinished(WebView v, String url) { capClient.onPageFinished(v, url); }
            @Override public void onReceivedError(WebView v, WebResourceRequest req, WebResourceError err) { capClient.onReceivedError(v, req, err); }
            @Override public void onReceivedHttpError(WebView v, WebResourceRequest req, WebResourceResponse resp) { capClient.onReceivedHttpError(v, req, resp); }
            @Override public void onReceivedSslError(WebView v, SslErrorHandler handler, SslError err) { capClient.onReceivedSslError(v, handler, err); }
        });
    }

    /** Returns true for URLs that should stay inside the WebView. */
    private boolean isInternalUrl(String url) {
        return url.startsWith("https://findjobsinfinland.fi/")
            || url.startsWith("http://findjobsinfinland.fi/")
            || url.startsWith("http://localhost")
            || url.startsWith("https://localhost")
            || url.startsWith("capacitor://")
            || url.startsWith("android-app://");
    }

    /** Opens a URL in a Chrome Custom Tab (in-app browser with brand toolbar colour). */
    private void openInCustomTab(String url) {
        try {
            CustomTabColorSchemeParams colorParams = new CustomTabColorSchemeParams.Builder()
                .setToolbarColor(Color.parseColor("#482dff"))
                .build();

            new CustomTabsIntent.Builder()
                .setShowTitle(true)
                .setDefaultColorSchemeParams(colorParams)
                .build()
                .launchUrl(this, Uri.parse(url));
        } catch (Exception e) {
            // Fallback: system browser if Custom Tabs not available
            try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url))); }
            catch (Exception ignored) { }
        }
    }
}

