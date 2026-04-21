/**
 * app-navigation.js
 * Platform-specific back button / swipe gesture navigation.
 *
 * Android:
 *   - If webview has history → go back
 *   - If on homepage → double-tap-to-exit with 2s window + toast
 *   - Else → go to homepage
 *
 * iOS:
 *   - Native swipe-back/forward gestures on WKWebView are enabled
 *     via capacitor.config.json (no JS required).
 *   - This file handles the edge-case: if history is empty, stay on home.
 *
 * Phase 4 — Platform-Specific Back Navigation
 */

(function () {
  'use strict';

  const HOME_PAGE = 'index.html';
  const BACK_EXIT_DELAY_MS = 2000;

  // Tracks whether the user pressed back once (Android double-tap-to-exit)
  let backPressedOnce = false;
  let backPressTimer = null;

  /**
   * Returns true if the current page is the home / index page.
   */
  function isHomePage() {
    const path = window.location.pathname;
    return (
      path === '/' ||
      path === '/index.html' ||
      path.endsWith('/index.html') ||
      path.endsWith('/nointernet.html') ||
      path === ''
    );
  }

  /**
   * Show a native-style toast message.
   * Uses the existing toastNotif() function if available, otherwise falls back.
   */
  function showToast(message) {
    if (typeof window.toastNotif === 'function') {
      window.toastNotif(message);
    } else if (
      window.Capacitor &&
      window.Capacitor.Plugins &&
      window.Capacitor.Plugins.Toast
    ) {
      window.Capacitor.Plugins.Toast.show({ text: message, duration: 'short' });
    } else {
      console.log('[AppNav] Toast:', message);
    }
  }

  /**
   * Exit the app via Capacitor App plugin.
   */
  function exitApp() {
    if (
      window.Capacitor &&
      window.Capacitor.Plugins &&
      window.Capacitor.Plugins.App
    ) {
      window.Capacitor.Plugins.App.exitApp();
    }
  }

  /**
   * Android hardware back button handler.
   * Called by Capacitor's backButton listener.
   */
  function handleAndroidBack() {
    if (window.history.length > 1 && document.referrer) {
      // Webview has navigable history → go back
      window.history.back();
      return;
    }

    if (isHomePage()) {
      if (backPressedOnce) {
        // Second press within window → exit
        clearTimeout(backPressTimer);
        backPressedOnce = false;
        exitApp();
      } else {
        // First press → show toast and set timer
        backPressedOnce = true;
        showToast('Press back again to exit');
        backPressTimer = setTimeout(function () {
          backPressedOnce = false;
        }, BACK_EXIT_DELAY_MS);
      }
    } else {
      // Not on homepage → go home
      window.location.href = HOME_PAGE;
    }
  }

  // ─── Register Capacitor back button listener (Android only) ──────────────────
  function registerBackButton() {
    if (!window.Capacitor) return;

    // Wait for Capacitor to be ready
    document.addEventListener('deviceready', function () {
      if (
        window.Capacitor.Plugins &&
        window.Capacitor.Plugins.App
      ) {
        window.Capacitor.Plugins.App.addListener(
          'backButton',
          handleAndroidBack
        );
      }
    }, false);

    // Also works outside Cordova/legacy — Capacitor fires this directly
    if (window.Capacitor.Plugins && window.Capacitor.Plugins.App) {
      window.Capacitor.Plugins.App.addListener(
        'backButton',
        handleAndroidBack
      );
    }
  }

  // ─── Register app state listener (resume behavior) ───────────────────────────
  function registerAppStateChange() {
    if (!window.Capacitor || !window.Capacitor.Plugins || !window.Capacitor.Plugins.App) return;

    window.Capacitor.Plugins.App.addListener('appStateChange', function (state) {
      if (state.isActive) {
        // App resumed from background — trigger silent refresh if data layer ready
        if (window.AppData && typeof window.AppData.silentRefresh === 'function') {
          window.AppData.silentRefresh();
        }
      }
    });
  }

  // ─── Init ────────────────────────────────────────────────────────────────────
  function init() {
    const platform = window.Capacitor ? window.Capacitor.getPlatform() : 'web';

    if (platform === 'android') {
      registerBackButton();
    }
    // iOS: swipe gestures are handled natively via WKWebView config
    // No JS needed for iOS back swipe

    registerAppStateChange();
  }

  // Run after DOM + Capacitor are ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // ─── Expose globally ─────────────────────────────────────────────────────────
  window.AppNav = {
    handleAndroidBack,
    isHomePage,
    showToast,
  };

})();
