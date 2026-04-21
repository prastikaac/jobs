package fi.findjobsinfinland.app;

import android.os.Bundle;
import android.webkit.WebView;
import android.graphics.Color;

import androidx.core.view.WindowCompat;
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {

    private SwipeRefreshLayout swipeRefreshLayout;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // ── Fix full-screen / dancing layout ────────────────────────────────────
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
                if (webView != null) {
                    // Call web-side refresh handler
                    webView.evaluateJavascript(
                        "if(window.AppPullToRefresh) window.AppPullToRefresh.onRefresh();",
                        null
                    );
                }
                // Listen for completion signal from JS
                listenForRefreshComplete();
            });

            // ── Only allow pull-to-refresh when scrolled to top ────────────────
            WebView webView = getBridge().getWebView();
            if (webView != null) {
                webView.getViewTreeObserver().addOnScrollChangedListener(() -> {
                    if (swipeRefreshLayout != null) {
                        // Disable pull-to-refresh when not at top of page
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

    /**
     * Poll until JS signals refresh is complete, then hide the spinner.
     * Uses evaluateJavascript to check a flag set by app-pull-to-refresh.js.
     */
    private void listenForRefreshComplete() {
        WebView webView = getBridge().getWebView();
        if (webView == null) return;

        // Listen for the DOM event via JS polling (simple, no plugin needed)
        webView.evaluateJavascript(
            "(function() {" +
            "  var done = false;" +
            "  document.addEventListener('app:refreshComplete', function() { done = true; }, {once: true});" +
            "  // Also set a max timeout of 8s" +
            "  setTimeout(function() { done = true; }, 8000);" +
            "  return 'listening';" +
            "})()",
            null
        );

        // Poll every 500ms up to 8 seconds
        final long startTime = System.currentTimeMillis();
        final android.os.Handler handler = new android.os.Handler(getMainLooper());
        final Runnable[] pollTask = {null};
        pollTask[0] = () -> {
            webView.evaluateJavascript(
                "document._appRefreshDone === true ? 'done' : 'waiting'",
                result -> {
                    long elapsed = System.currentTimeMillis() - startTime;
                    if ("'done'".equals(result) || elapsed >= 8000) {
                        if (swipeRefreshLayout != null) {
                            swipeRefreshLayout.setRefreshing(false);
                        }
                    } else {
                        handler.postDelayed(pollTask[0], 500);
                    }
                }
            );
        };
        // Set the flag in JS, then start polling
        webView.evaluateJavascript(
            "document.addEventListener('app:refreshComplete', function() { document._appRefreshDone = true; }, {once: true});",
            null
        );
        handler.postDelayed(pollTask[0], 500);
    }
}
