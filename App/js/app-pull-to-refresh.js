/**
 * app-pull-to-refresh.js
 * Web-side handler for pull-to-refresh events triggered from native.
 *
 * Android: SwipeRefreshLayout calls window.AppPullToRefresh.onRefresh()
 * iOS:     UIRefreshControl calls window.AppPullToRefresh.onRefresh()
 *
 * This script is called BY the native layer.
 * The native implementations are configured in the Android/iOS project files.
 *
 * Phase 5 — Pull-to-Refresh
 */

(function () {
  'use strict';

  var refreshInProgress = false;

  /**
   * Called by native SwipeRefreshLayout (Android) or UIRefreshControl (iOS).
   * Refreshes the data for the current page, then signals completion.
   */
  function onRefresh() {
    if (refreshInProgress) return;
    refreshInProgress = true;

    var page = getCurrentPage();

    if (page === 'jobs') {
      // Trigger a fresh data load, bypassing cache maxAge
      if (window.AppData && typeof window.AppData.loadJobs === 'function') {
        window.AppData.loadJobs(function (data, meta) {
          // Fire a DOM event so jobs.html can re-render its list
          document.dispatchEvent(new CustomEvent('app:jobsRefreshed', { detail: data }));
          // Signal native that refresh is done
          signalDone();
        }, { maxAgeMs: 0 }); // force network fetch
      } else {
        // Fallback: reload the page
        window.location.reload();
        return; // don't signal done — page is reloading
      }
    } else {
      // For non-jobs pages: full page reload
      window.location.reload();
    }
  }

  /**
   * Signal the native layer that refresh is complete (hides spinner).
   * Calls into Capacitor plugins or falls back to a global callback.
   */
  function signalDone() {
    refreshInProgress = false;

    // Notify native via Capacitor message bridge
    if (window.Capacitor && window.Capacitor.nativeCallback) {
      window.Capacitor.nativeCallback('refreshComplete');
    }

    // Also dispatch DOM event in case other JS is listening
    document.dispatchEvent(new CustomEvent('app:refreshComplete'));
  }

  /**
   * Returns the logical name of the current page.
   */
  function getCurrentPage() {
    var path = window.location.pathname;
    if (path.indexOf('jobs') !== -1) return 'jobs';
    if (path.indexOf('about') !== -1) return 'about';
    if (path.indexOf('contact') !== -1) return 'contact';
    return 'home';
  }

  // ─── Expose globally (called by native code) ──────────────────────────────────
  window.AppPullToRefresh = {
    onRefresh: onRefresh,
    signalDone: signalDone,
  };

})();
