package fi.findjobsinfinland.app;

import android.os.Bundle;
import android.os.Handler;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.graphics.Color;
import android.widget.Toast;

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
}

