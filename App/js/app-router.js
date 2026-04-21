/**
 * app-router.js
 * Intercepts all navigation and routes findjobsinfinland.fi URLs
 * to live remote pages. External links open in in-app browser.
 */

(function () {
  'use strict';

  const APP_DOMAIN = 'findjobsinfinland.fi';

  // ─── Helpers ─────────────────────────────────────────────────────────────────

  /**
   * Open a URL in the system browser via Capacitor Browser plugin.
   */
  function openExternal(url) {
    if (
      window.Capacitor &&
      window.Capacitor.Plugins &&
      window.Capacitor.Plugins.Browser
    ) {
      window.Capacitor.Plugins.Browser.open({ url });
    } else {
      window.open(url, '_blank');
    }
  }

  // ─── App Open Redirect ────────────────────────────────────────────────────────
  
  // If we are on the local root index.html, redirect immediately to the live site.
  // This effectively removes the need for local files and makes the app load the live domain.
  if (
    window.location.hostname === 'localhost' ||
    window.location.hostname === '127.0.0.1' ||
    window.location.hostname === '' ||
    window.location.protocol === 'file:'
  ) {
    if (window.location.pathname.endsWith('index.html') || window.location.pathname === '/' || window.location.pathname === '') {
       if (navigator.onLine) {
         window.location.replace(`https://${APP_DOMAIN}/`);
       } else {
         window.location.replace('nointernet.html');
       }
    }
  }

  // ─── Click interception ───────────────────────────────────────────────────────
  document.addEventListener('click', function (e) {
    const anchor = e.target.closest('a[href]');
    if (!anchor) return;

    const href = anchor.getAttribute('href');
    if (!href || href.startsWith('#') || href.startsWith('javascript:')) return;

    // Skip mailto / tel links
    if (href.startsWith('mailto:') || href.startsWith('tel:')) return;

    let parsed;
    try {
      parsed = new URL(href, window.location.href);
    } catch (err) {
      return; // Invalid URL, let default behavior happen
    }

    const isAppDomain =
      parsed.hostname === APP_DOMAIN ||
      parsed.hostname === 'www.' + APP_DOMAIN ||
      parsed.hostname === '' ||
      parsed.hostname === window.location.hostname ||
      parsed.hostname === 'localhost';

    if (isAppDomain) {
      // Internal link -> open directly in the WebView
      e.preventDefault();

      if (!navigator.onLine) {
        // Offline → show no-internet page
        try { sessionStorage.setItem('app_last_page_before_offline', window.location.href); } catch (_) {}
        window.location.href = 'nointernet.html';
        return;
      }

      // Ensure we point to the remote server, not localhost
      let targetUrl = anchor.href;
      if (
        parsed.hostname === '' ||
        parsed.hostname === 'localhost' ||
        parsed.hostname === '127.0.0.1' ||
        parsed.hostname === window.location.hostname
      ) {
        if (targetUrl.startsWith('file://')) {
          targetUrl = `https://${APP_DOMAIN}${parsed.pathname}${parsed.search}${parsed.hash}`;
        } else {
          targetUrl = `https://${APP_DOMAIN}${parsed.pathname}${parsed.search}${parsed.hash}`;
        }
      }

      try {
        window.location.href = targetUrl;
      } catch (err) {
        window.location.href = href;
      }
    } else {
      // External link -> open in browser mode inside the app
      e.preventDefault();

      if (!navigator.onLine) {
        // Offline → show no-internet page
        try { sessionStorage.setItem('app_last_page_before_offline', window.location.href); } catch (_) {}
        window.location.href = 'nointernet.html';
        return;
      }

      openExternal(anchor.href);
    }
  }, true); // capture phase to intercept before other handlers

  // ─── Expose globally ─────────────────────────────────────────────────────────
  window.AppRouter = {
    openExternal,
  };

})();
