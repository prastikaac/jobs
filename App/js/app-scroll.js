/**
 * app-scroll.js
 * Scroll position memory — saves/restores scroll position per route.
 * When the user navigates back, they return to where they were.
 *
 * Phase 7 — Scroll & Resume Behavior
 */

(function () {
  'use strict';

  const STORAGE_KEY = 'app_scroll_positions';
  const MAX_STORED_ROUTES = 20; // limit memory usage

  // ─── Storage helpers ─────────────────────────────────────────────────────────

  function loadPositions() {
    try {
      return JSON.parse(sessionStorage.getItem(STORAGE_KEY) || '{}');
    } catch (_) {
      return {};
    }
  }

  function savePositions(positions) {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(positions));
    } catch (_) { /* storage full or unavailable — silently skip */ }
  }

  // ─── Public API ───────────────────────────────────────────────────────────────

  /**
   * Save the current scroll position for a given route key.
   * @param {string} routeKey - e.g. 'jobs.html?q=cleaning'
   */
  function save(routeKey) {
    if (!routeKey) routeKey = currentRouteKey();
    const positions = loadPositions();

    // Evict oldest entry if over limit
    const keys = Object.keys(positions);
    if (keys.length >= MAX_STORED_ROUTES) {
      delete positions[keys[0]];
    }

    positions[routeKey] = {
      x: window.scrollX || 0,
      y: window.scrollY || 0,
      ts: Date.now(),
    };
    savePositions(positions);
  }

  /**
   * Restore scroll position for a given route key.
   * Waits for content to render before scrolling.
   * @param {string} [routeKey] - defaults to current page
   */
  function restore(routeKey) {
    if (!routeKey) routeKey = currentRouteKey();
    const positions = loadPositions();
    const pos = positions[routeKey];
    if (!pos) return;

    // Use requestAnimationFrame to ensure DOM has painted
    requestAnimationFrame(function () {
      window.scrollTo({ top: pos.y, left: pos.x, behavior: 'instant' });
    });
  }

  /**
   * Clear saved position for a route (e.g. after a hard refresh).
   */
  function clear(routeKey) {
    if (!routeKey) routeKey = currentRouteKey();
    const positions = loadPositions();
    delete positions[routeKey];
    savePositions(positions);
  }

  /**
   * Returns a consistent key for the current page (path + search).
   */
  function currentRouteKey() {
    return (window.location.pathname + window.location.search).replace(/^\//, '');
  }

  // ─── Auto-save on unload ──────────────────────────────────────────────────────
  // Save scroll position just before the user navigates away
  window.addEventListener('pagehide', function () {
    save(currentRouteKey());
  });

  // Also save on visibility change (covers background on mobile)
  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'hidden') {
      save(currentRouteKey());
    }
  });

  // ─── Auto-restore on page load ────────────────────────────────────────────────
  // Restore scroll after page paints (only on back navigation via History API)
  window.addEventListener('pageshow', function (e) {
    if (e.persisted) {
      // Restored from bfcache (back/forward)
      restore(currentRouteKey());
    }
  });

  // For jobs.html — restore after dynamic job cards are injected
  // Other pages can call AppScroll.restore() manually after their data loads
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      // Small delay to allow dynamic content to render first
      setTimeout(function () {
        restore(currentRouteKey());
      }, 150);
    });
  } else {
    setTimeout(function () {
      restore(currentRouteKey());
    }, 150);
  }

  // ─── Expose globally ─────────────────────────────────────────────────────────
  window.AppScroll = {
    save,
    restore,
    clear,
    currentRouteKey,
  };

})();
