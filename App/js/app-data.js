/**
 * app-data.js
 * Data-fetching layer with instant-load caching strategy.
 *
 * Philosophy:
 *   - Show cached data IMMEDIATELY on open (no blank screen)
 *   - Fetch fresh data from JSON APIs in the background
 *   - Update UI silently when new data arrives
 *   - Never show a loading screen unless absolutely necessary
 *
 * Phase 3 — Data Layer (JSON API)
 */

(function () {
  'use strict';

  const CACHE_VERSION = 'v1';
  const CACHE_KEY_PREFIX = 'appdata_' + CACHE_VERSION + '_';

  // ─── Cache helpers ────────────────────────────────────────────────────────────

  function cacheGet(key) {
    try {
      const raw = localStorage.getItem(CACHE_KEY_PREFIX + key);
      if (!raw) return null;
      const entry = JSON.parse(raw);
      return entry;
    } catch (_) {
      return null;
    }
  }

  function cacheSet(key, data) {
    try {
      localStorage.setItem(CACHE_KEY_PREFIX + key, JSON.stringify({
        data: data,
        ts: Date.now(),
      }));
    } catch (_) {
      // Storage full — clear old cache entries and retry
      clearOldCache();
    }
  }

  function clearOldCache() {
    try {
      const keysToRemove = [];
      for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i);
        if (k && k.startsWith('appdata_') && !k.startsWith(CACHE_KEY_PREFIX)) {
          keysToRemove.push(k);
        }
      }
      keysToRemove.forEach(function (k) { localStorage.removeItem(k); });
    } catch (_) { /* ignore */ }
  }

  // ─── Fetch with timeout ───────────────────────────────────────────────────────

  function fetchWithTimeout(url, timeoutMs) {
    timeoutMs = timeoutMs || 8000;
    const controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
    const timer = controller
      ? setTimeout(function () { controller.abort(); }, timeoutMs)
      : null;

    const options = controller ? { signal: controller.signal } : {};

    return fetch(url, options).then(function (res) {
      if (timer) clearTimeout(timer);
      if (!res.ok) throw new Error('HTTP ' + res.status);
      return res.json();
    }).catch(function (err) {
      if (timer) clearTimeout(timer);
      throw err;
    });
  }

  // ─── Core fetch strategy ──────────────────────────────────────────────────────

  /**
   * Fetch data for a named resource.
   *
   * @param {string} key        - Cache key (e.g. 'jobs', 'categories')
   * @param {string} url        - JSON API endpoint
   * @param {function} onData   - Called with data whenever available (cache or fresh)
   * @param {object}  [opts]
   * @param {number}  [opts.maxAgeMs]  - Skip network if cache is younger than this (default 5 min)
   */
  function load(key, url, onData, opts) {
    opts = opts || {};
    const maxAgeMs = opts.maxAgeMs !== undefined ? opts.maxAgeMs : 5 * 60 * 1000;

    // 1. Show cached data immediately
    const cached = cacheGet(key);
    if (cached && cached.data) {
      onData(cached.data, { fromCache: true });

      // If cache is fresh enough, skip network fetch
      const age = Date.now() - (cached.ts || 0);
      if (age < maxAgeMs) return;
    }

    // 2. Background fetch for fresh data
    fetchWithTimeout(url).then(function (freshData) {
      cacheSet(key, freshData);
      onData(freshData, { fromCache: false });
    }).catch(function (err) {
      // Silent failure — cached data already shown
      console.warn('[AppData] Background fetch failed for', key, err.message);
    });
  }

  /**
   * Force a silent refresh of all cached resources.
   * Called by app-navigation.js on app resume.
   */
  function silentRefresh() {
    // Dispatch a custom event so pages can react to it if needed
    document.dispatchEvent(new CustomEvent('app:silentRefresh'));
  }

  // ─── Named resources ──────────────────────────────────────────────────────────
  // These are the known JSON endpoints. Update URLs as the backend grows.

  const ENDPOINTS = {
    jobs:       'https://findjobsinfinland.fi/api/jobs.json',
    categories: 'https://findjobsinfinland.fi/api/categories.json',
  };

  /**
   * Load jobs data.
   * @param {function} onData - Called with jobs array
   * @param {object}  [opts]
   */
  function loadJobs(onData, opts) {
    load('jobs', ENDPOINTS.jobs, onData, opts);
  }

  /**
   * Load categories data.
   * @param {function} onData - Called with categories array
   * @param {object}  [opts]
   */
  function loadCategories(onData, opts) {
    load('categories', ENDPOINTS.categories, onData, opts);
  }

  // ─── Expose globally ─────────────────────────────────────────────────────────
  window.AppData = {
    load,
    loadJobs,
    loadCategories,
    silentRefresh,
    cacheGet,
    cacheSet,
    ENDPOINTS,
  };

})();
