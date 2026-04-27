/**
 * app-pull-to-refresh.js
 * Web-side handler for pull-to-refresh events triggered from native iOS/Android.
 *
 * Android: SwipeRefreshLayout calls window.AppPullToRefresh.onRefresh()
 * iOS:     UIRefreshControl → ViewController patches signalDone then calls onRefresh()
 *          The patch posts webkit.messageHandlers.refreshComplete back to hide the spinner.
 *
 * Phase 5 — Pull-to-Refresh
 */

(function () {
  'use strict';

  var refreshInProgress = false;

  /**
   * Called by native (Android SwipeRefreshLayout or iOS UIRefreshControl bridge).
   * Refreshes data for the current page, then signals completion via signalDone().
   */
  function onRefresh() {
    if (refreshInProgress) return;
    refreshInProgress = true;

    var page = getCurrentPage();

    if (page === 'jobs') {
      if (window.AppData && typeof window.AppData.loadJobs === 'function') {
        window.AppData.loadJobs(function (data) {
          document.dispatchEvent(new CustomEvent('app:jobsRefreshed', { detail: data }));
          signalDone();
        }, { maxAgeMs: 0 }); // force network fetch, bypass cache
      } else {
        // AppData not ready yet — full reload (native spinner ends via didFinish)
        window.location.reload();
      }
    } else {
      // All non-jobs pages: full page reload
      window.location.reload();
    }
  }

  /**
   * Signal the native layer that the refresh is complete (hides spinner).
   *
   * On iOS, ViewController.swift patches this function before calling onRefresh()
   * so it also posts to webkit.messageHandlers.refreshComplete.
   * On Android, Capacitor's nativeCallback is used if available.
   */
  function signalDone() {
    refreshInProgress = false;

    // Android / generic Capacitor callback
    if (window.Capacitor && window.Capacitor.nativeCallback) {
      window.Capacitor.nativeCallback('refreshComplete');
    }

    // Dispatch DOM event so other JS listeners can react
    document.dispatchEvent(new CustomEvent('app:refreshComplete'));

    // NOTE: On iOS the native ViewController patches this function before
    // calling onRefresh(), adding a webkit.messageHandlers.refreshComplete
    // postMessage call. No extra code needed here for that path.
  }

  /**
   * Returns the logical name of the current page based on the URL path.
   */
  function getCurrentPage() {
    var path = window.location.pathname;
    if (path.indexOf('jobs') !== -1) return 'jobs';
    if (path.indexOf('about') !== -1) return 'about';
    if (path.indexOf('contact') !== -1) return 'contact';
    return 'home';
  }

  // ─── Expose globally (called by native code) ─────────────────────────────────
  window.AppPullToRefresh = {
    onRefresh: onRefresh,
    signalDone: signalDone,
  };

})();