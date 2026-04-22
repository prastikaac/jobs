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
import com.getcapacitor.WebViewListener;

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
                    getBridge().getWebView().loadUrl("https://localhost/nointernet.html");
                });
            }
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

                // Inject JS to handle external links via Capacitor Browser plugin and instant offline catch
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
                            "    } else if (!navigator.onLine) {" +
                            "      e.preventDefault();" +
                            "      sessionStorage.setItem('app_last_page_before_offline', a.href);" +
                            "      window.location.href = 'https://localhost/nointernet.html';" +
                            "    }" +
                            "  }" +
                            "};" +
                            "document.addEventListener('click', window._capLinkInterceptor, true);";
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

        swipeRefreshLayout.setColorSchemeColors(
            Color.parseColor("#482dff"),
            Color.parseColor("#6c52ff"),
            Color.parseColor("#8a79ff")
        );

        swipeRefreshLayout.setOnRefreshListener(() -> {
            if (!isConnected()) {
                swipeRefreshLayout.setRefreshing(false);
                wv.evaluateJavascript("sessionStorage.setItem('app_last_page_before_offline', window.location.href); window.location.href = 'https://localhost/nointernet.html';", null);
                return;
            }

            // DO NOT use wv.reload() natively as it destroys Capacitor's JS bridge hooks and causes a fatal crash
            wv.evaluateJavascript("window.location.reload(true);", null);

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
