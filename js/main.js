/*<![CDATA[*/
(function () {
    var style = document.createElement('style');
    style.innerHTML = '.tBkmt:not([data-text])::before, .tBkmt[data-text="0"]::before, .tBkmt[data-text=""]::before { display: none !important; content: none !important; padding: 0 !important; background: transparent !important; }';
    document.head.appendChild(style);

    function syncBkmBadge() {
        var src = document.querySelector('.isBkm .tBkmt');
        var dst = document.querySelector('.mN .tBkmt');
        if (!src || !dst) return;
        var val = src.getAttribute('data-text');
        if (val !== null && parseInt(val, 10) >= 1) {
            dst.setAttribute('data-text', val);
        } else {
            dst.removeAttribute('data-text');
            if (val === '0' || val === '') {
                src.removeAttribute('data-text');
            }
        }
    }
    function init() {
        syncBkmBadge();
        var src = document.querySelector('.isBkm .tBkmt');
        if (src) {
            new MutationObserver(syncBkmBadge).observe(src, { attributes: true, attributeFilter: ['data-text'] });
        }
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
/*]]>*/

/* ── GTranslate: show short language code (e.g. EN, FI, NE) instead of full name ── */
(function () {
    function shortenGtLabel() {
        // The trigger button: <a class="gt_switcher-popup ..."><img alt="en"> <span>English</span> ...
        var btn = document.querySelector('.gt_switcher-popup');
        if (!btn) return;
        var img  = btn.querySelector('img');
        var span = btn.querySelector('span:not([style])');
        if (!img || !span) return;
        var code = (img.alt || '').replace(/[^a-zA-Z]/g, '').toUpperCase();
        if (code && span.textContent !== code) {
            span.textContent = code;
        }
    }

    // Run once as soon as the element exists, then watch for GTranslate's async updates
    function start() {
        shortenGtLabel();
        var observer = new MutationObserver(shortenGtLabel);
        observer.observe(document.body, { childList: true, subtree: true, characterData: true });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', start);
    } else {
        start();
    }
})();