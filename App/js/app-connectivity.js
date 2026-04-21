/**
 * app-connectivity.js
 * Monitors network connectivity and shows the "No Internet" page
 * when the device goes offline. Automatically navigates back to the
 * previous page when connectivity is restored.
 *
 * Strategy:
 *   - Listen to the native browser online/offline events
 *   - On Capacitor (Android/iOS), also listen via Network plugin if available
 *   - When offline  → save current URL and navigate to nointernet.html
 *   - When online   → navigate back to the saved URL (or index.html)
 *   - On nointernet.html → poll every 3s so the retry button also works
 *
 * Phase 6 — Connectivity Handling
 */

(function () {
  'use strict';

  const NO_INTERNET_PAGE = 'nointernet.html';
  const STORAGE_KEY = 'app_last_page_before_offline';
  const POLL_INTERVAL_MS = 3000;

  let pollTimer = null;
  let isOnNoInternetPage = false;

  // ─── Helpers ─────────────────────────────────────────────────────────────────

  function currentPath() {
    return window.location.pathname + window.location.search + window.location.hash;
  }

  function isOfflinePage() {
    return window.location.pathname.endsWith(NO_INTERNET_PAGE);
  }

  function saveCurrentPage() {
    if (!isOfflinePage()) {
      try {
        sessionStorage.setItem(STORAGE_KEY, currentPath());
      } catch (_) {}
    }
  }

  function getSavedPage() {
    try {
      return sessionStorage.getItem(STORAGE_KEY) || 'index.html';
    } catch (_) {
      return 'index.html';
    }
  }

  function clearSavedPage() {
    try {
      sessionStorage.removeItem(STORAGE_KEY);
    } catch (_) {}
  }

  // ─── Go offline ───────────────────────────────────────────────────────────────

  function handleOffline() {
    if (isOfflinePage()) return; // already showing no-internet page

    saveCurrentPage();
    stopPolling();
    window.location.href = NO_INTERNET_PAGE;
  }

  // ─── Go online ────────────────────────────────────────────────────────────────

  function handleOnline() {
    stopPolling();

    if (!isOfflinePage()) {
      clearSavedPage();
      return; // came back online on a normal page — nothing to do
    }

    // We are on the no-internet page → navigate back
    const returnTo = getSavedPage();
    clearSavedPage();
    window.location.href = returnTo;
  }

  // ─── Polling (used on nointernet.html to auto-detect reconnection) ────────────

  function startPolling() {
    if (pollTimer) return;
    pollTimer = setInterval(checkConnectivity, POLL_INTERVAL_MS);
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  /**
   * Lightweight connectivity check — tries to fetch a tiny resource.
   * navigator.onLine alone can lie on Android.
   */
  function checkConnectivity() {
    // Fast check first
    if (!navigator.onLine) return;

    // Deep check: ping a known tiny resource
    const probe = 'https://findjobsinfinland.fi/images/icon.png?_=' + Date.now();
    fetch(probe, { method: 'HEAD', cache: 'no-store', mode: 'no-cors' })
      .then(function () {
        handleOnline();
      })
      .catch(function () {
        // Still offline — keep polling
      });
  }

  // ─── Retry button on nointernet.html ─────────────────────────────────────────

  function bindRetryButton() {
    // Wait for DOM to be ready
    function tryBind() {
      const btn = document.querySelector('.cta');
      if (btn) {
        btn.addEventListener('click', function () {
          // Visual feedback: spin the icon
          const icon = btn.querySelector('.icon');
          if (icon) {
            icon.style.transition = 'transform 0.5s ease';
            icon.style.transform = 'rotate(360deg)';
            setTimeout(function () {
              icon.style.transform = '';
            }, 500);
          }
          checkConnectivity();
        });
      }
    }

    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', tryBind);
    } else {
      tryBind();
    }
  }

  // ─── Capacitor Network plugin (optional, better accuracy on native) ───────────

  function registerCapacitorNetwork() {
    if (
      !window.Capacitor ||
      !window.Capacitor.Plugins ||
      !window.Capacitor.Plugins.Network
    ) return;

    const Network = window.Capacitor.Plugins.Network;

    // Get initial status
    Network.getStatus().then(function (status) {
      if (!status.connected && !isOfflinePage()) {
        handleOffline();
      }
    }).catch(function () {});

    // Listen for changes
    Network.addListener('networkStatusChange', function (status) {
      if (status.connected) {
        handleOnline();
      } else {
        handleOffline();
      }
    });
  }

  // ─── Init ────────────────────────────────────────────────────────────────────

  function init() {
    // Standard browser events
    window.addEventListener('offline', handleOffline);
    window.addEventListener('online', handleOnline);

    if (isOfflinePage()) {
      // We are on the no-internet page — start polling and bind retry
      isOnNoInternetPage = true;
      bindRetryButton();
      startPolling();
    } else {
      // Normal page — check connectivity proactively once
      if (!navigator.onLine) {
        handleOffline();
      }
    }

    // Capacitor native network events (best accuracy)
    registerCapacitorNetwork();
  }

  // Run after DOM is available
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // ─── Expose globally ─────────────────────────────────────────────────────────
  window.AppConnectivity = {
    checkConnectivity,
    handleOffline,
    handleOnline,
  };

})();
