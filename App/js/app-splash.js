/**
 * app-splash.js
 * Controls the splash screen lifecycle.
 *
 * Flow:
 *   1. Splash is shown natively via @capacitor/splash-screen (launchAutoHide: false)
 *   2. index.html loads in background
 *   3. Once DOMContentLoaded fires + a small buffer → hide splash
 *   4. Total visible splash time: ~1–2 seconds
 *
 * Phase 6 — Splash Screen
 */

(function () {
  'use strict';

  // Minimum visible time for splash (ms) — feels intentional, not janky
  const MIN_SPLASH_MS = 800;

  const splashStart = Date.now();

  function hideSplash() {
    const elapsed = Date.now() - splashStart;
    const remaining = Math.max(0, MIN_SPLASH_MS - elapsed);

    setTimeout(function () {
      if (
        window.Capacitor &&
        window.Capacitor.Plugins &&
        window.Capacitor.Plugins.SplashScreen
      ) {
        window.Capacitor.Plugins.SplashScreen.hide({
          fadeOutDuration: 300,
        });
      }
    }, remaining);
  }

  // Hide once DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', hideSplash);
  } else {
    hideSplash();
  }

  window.AppSplash = { hideSplash };

})();
