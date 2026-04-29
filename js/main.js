/*<![CDATA[*/
(function () {
    function syncBkmBadge() {
        var src = document.querySelector('.isBkm .tBkmt');
        var dst = document.querySelector('.mN .tBkmt');
        if (!src || !dst) return;
        var val = src.getAttribute('data-text');
        if (val !== null && parseInt(val, 10) >= 1) {
            dst.setAttribute('data-text', val);
        } else {
            dst.removeAttribute('data-text');
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