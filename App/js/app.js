/**
 * app.js
 * Main entry point — loads all app modules in the correct order.
 * Include this single script in every bundled HTML page.
 *
 * Load order:
 *   1. app-splash.js    — hide splash ASAP after DOM ready
 *   2. app-scroll.js    — restore scroll position
 *   3. app-router.js    — intercept navigation clicks
 *   4. app-data.js      — data caching layer
 *   5. app-navigation.js — back button / app resume
 */

(function () {
  'use strict';

  // Only run inside Capacitor native app
  // (safe to include on web too; modules self-guard with window.Capacitor checks)

  var BASE = (function () {
    // Detect if we are served from a local file vs remote
    var scripts = document.getElementsByTagName('script');
    for (var i = 0; i < scripts.length; i++) {
      var src = scripts[i].src;
      if (src && src.indexOf('app.js') !== -1) {
        return src.replace('app.js', '');
      }
    }
    return 'js/';
  })();

  var MODULES = [
    'app-splash.js',
    'app-scroll.js',
    'app-router.js',
    'app-data.js',
    'app-connectivity.js',
    'app-pull-to-refresh.js',
    'app-navigation.js',
  ];

  function loadScript(src, callback) {
    var el = document.createElement('script');
    el.src = src;
    el.async = false;
    if (callback) el.onload = callback;
    document.head.appendChild(el);
  }

  // Load modules sequentially (order matters)
  (function loadNext(i) {
    if (i >= MODULES.length) return;
    loadScript(BASE + MODULES[i], function () {
      loadNext(i + 1);
    });
  })(0);

})();
