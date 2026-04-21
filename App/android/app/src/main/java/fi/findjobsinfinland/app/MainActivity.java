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
