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
    }

    @Override
    public void onPause() {
        super.onPause();
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) WindowCompat.setDecorFitsSystemWindows(getWindow(), true);
    }

    // =============================================================================
    //  Link Interception for In-App Browser (Custom Tabs)
    // =============================================================================

    private void setupLinkInterception() {
        WebView wv = getBridge().getWebView();
        if (wv == null) return;

        WebViewClient capClient = wv.getWebViewClient();

        wv.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                String url = request.getUrl().toString();
                if (isOwnSiteUrl(url) || isBundledUrl(url)) {
                    if (!isBundledUrl(url) && !isConnected()) {
                        view.loadUrl("file:///android_asset/public/nointernet.html");
                        return true;
                    }
                    return capClient.shouldOverrideUrlLoading(view, request);
                }
                
                final String targetUrl = url;
                new Handler(Looper.getMainLooper()).post(() -> openInCustomTab(targetUrl));
                return true;
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, String url) {
                if (isOwnSiteUrl(url) || isBundledUrl(url)) {
                    if (!isBundledUrl(url) && !isConnected()) {
                        view.loadUrl("file:///android_asset/public/nointernet.html");
                        return true;
                    }
                    return capClient.shouldOverrideUrlLoading(view, url);
                }
                
                final String targetUrl = url;
                new Handler(Looper.getMainLooper()).post(() -> openInCustomTab(targetUrl));
                return true;
            }

            @Override public WebResourceResponse shouldInterceptRequest(WebView v, WebResourceRequest req) { return capClient.shouldInterceptRequest(v, req); }
            @Override public WebResourceResponse shouldInterceptRequest(WebView v, String url) { return capClient.shouldInterceptRequest(v, url); }
            @Override public void onPageStarted(WebView v, String url, Bitmap fav) { capClient.onPageStarted(v, url, fav); }
            @Override public void onPageFinished(WebView v, String url) { 
                capClient.onPageFinished(v, url); 
                // Hide splash screen explicitly when the live website finishes loading
                v.evaluateJavascript("if (window.Capacitor && window.Capacitor.Plugins.SplashScreen) { window.Capacitor.Plugins.SplashScreen.hide(); }", null);
            }
            
            @Override 
            public void onReceivedError(WebView v, WebResourceRequest req, WebResourceError err) { 
                if (req.isForMainFrame()) {
                    v.loadUrl("file:///android_asset/public/nointernet.html");
                    return;
                }
                capClient.onReceivedError(v, req, err); 
            }
            
            @Override 
            public void onReceivedError(WebView v, int code, String desc, String url) { 
                v.loadUrl("file:///android_asset/public/nointernet.html");
            }
            
            @Override public void onReceivedHttpError(WebView v, WebResourceRequest req, WebResourceResponse resp) { capClient.onReceivedHttpError(v, req, resp); }
            @Override public void onReceivedSslError(WebView v, SslErrorHandler h, SslError err) { capClient.onReceivedSslError(v, h, err); }
        });
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

    private boolean isOwnSiteUrl(String url) {
        return url.startsWith("https://findjobsinfinland.fi/")
            || url.startsWith("http://findjobsinfinland.fi/");
    }

    private boolean isBundledUrl(String url) {
        return url.startsWith("http://localhost")
            || url.startsWith("https://localhost")
            || url.startsWith("capacitor://")
            || url.startsWith("android-app://")
            || url.startsWith("file:///android_asset/");
    }

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

            if (!isConnected()) {
                swipeRefreshLayout.setRefreshing(false);
                wv.loadUrl("file:///android_asset/public/nointernet.html");
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

        // Let the WebView navigate back normally
        if (wv != null && wv.canGoBack()) {
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
}
