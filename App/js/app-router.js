/**
 * app-router.js
 * Intercepts all navigation and routes findjobsinfinland.fi URLs
 * to local bundled HTML pages instead of making network requests.
 *
 * Phase 2 - Local Page Routing & URL Interception
 */

(function () {
  'use strict';

  // --- Local page map ----------------------------------------------------------
  // Maps findjobsinfinland.fi pathname -> local bundled file
  const LOCAL_ROUTES = {
    '/':                        'index.html',
    '/jobs':                    'jobs.html',
    '/about-us':               'about-us.html',
    '/contact-us':             'contact-us.html',
    '/edit-profile':           'edit-profile.html',
    '/privacy-policy':         'privacy-policy.html',
    '/terms-and-conditions':   'terms-and-conditions.html',
    '/disclaimer':             'disclaimer.html',
    '/404':                    '404.html',
    '/nointernet':             'nointernet.html',
  };

  const APP_DOMAIN = 'findjobsinfinland.fi';

  // --- Helpers -----------------------------------------------------------------

  /**
   * Returns the local file path for a given URL, or null if it's external.
   * Preserves query strings (e.g. ?q=cleaning&location=Helsinki).
   */
  function resolveLocal(url) {
    let parsed;
    try {
      // Handle relative URLs by resolving against current origin
      parsed = new URL(url, window.location.href);
    } catch (e) {
      return null;
    }

    const isAppDomain =
      parsed.hostname === APP_DOMAIN ||
      parsed.hostname === '' ||
      parsed.hostname === window.location.hostname;

    if (!isAppDomain) return null; // external link

    // Normalize path: strip trailing slash (except root)
    let path = parsed.pathname.replace(/\/$/, '') || '/';

    // Strip .html extension if present (canonical form)
    path = path.replace(/\.html$/, '');

    const localFile = LOCAL_ROUTES[path];
    if (!localFile) return null;

    // Preserve query string and hash
    const qs = parsed.search ? parsed.search : '';
    const hash = parsed.hash ? parsed.hash : '';
    return localFile + qs + hash;
  }

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

  // --- Click interception -------------------------------------------------------
  document.addEventListener('click', function (e) {
    const anchor = e.target.closest('a[href]');
    if (!anchor) return;

    const href = anchor.getAttribute('href');
    if (!href || href.startsWith('#') || href.startsWith('javascript:')) return;

    // Skip mailto / tel links
    if (href.startsWith('mailto:') || href.startsWith('tel:')) return;

    const localPath = resolveLocal(href);

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

    if (localPath) {
      // Internal mapped -> navigate to bundled local page
      e.preventDefault();
      navigateTo(localPath);
    } else if (isAppDomain) {
      // Internal unmapped (e.g. /cleaner.html) -> open directly in the WebView
      e.preventDefault();

      if (!navigator.onLine) {
        // Offline -> show no-internet page
        try { sessionStorage.setItem('app_last_page_before_offline', window.location.href); } catch (_) {}
        navigateTo('nointernet.html');
        return;
      }

      // Ensure we point to the remote server, not localhost
      let targetUrl = anchor.href;
      if (
        parsed.hostname === '' ||
        parsed.hostname === 'localhost' ||
        parsed.hostname === '127.0.0.1' ||
        parsed.hostname === window.location.hostname ||
        targetUrl.startsWith('file://') || targetUrl.includes('localhost')
      ) {
        targetUrl = 'https://' + APP_DOMAIN + parsed.pathname + parsed.search + parsed.hash;
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
        // Offline -> show no-internet page
        try { sessionStorage.setItem('app_last_page_before_offline', window.location.href); } catch (_) {}
        navigateTo('nointernet.html');
        return;
      }

      openExternal(anchor.href);
    }
  }, true); // capture phase to intercept before other handlers

  // --- Navigation ---------------------------------------------------------------

  /**
   * Navigate to a local page, saving scroll position of current page first.
   */
  function navigateTo(localPath) {
    // Save current scroll before leaving
    if (window.AppScroll && typeof window.AppScroll.save === 'function') {
      window.AppScroll.save(window.location.pathname + window.location.search);
    }
    window.location.href = localPath;
  }

  // --- Expose globally ---------------------------------------------------------
  window.AppRouter = {
    resolveLocal,
    navigateTo,
    openExternal,
  };

})();
