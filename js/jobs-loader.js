/**
 * jobs-loader.js
 * Fetches scraper/data/jobs.json on every page load and renders
 * <article class="ntry"> cards into #Blog1 .blogPts
 * using the EXACT same HTML structure the pipeline generator produces.
 *
 * Now supports client-side pagination:
 *  - window.JobsPagination  → public API used by inline filter/pagination script
 *  - Pagination renders only `perPage` jobs at a time, filtered set is sliced.
 */
(function () {
  "use strict";

  /* ── Config ─────────────────────────────────────────────────────────── */
  var JOBS_JSON_URL = "QuantumNeuralHyperSync_ArchiveVaultX9_UltraSecureDataMatrix_EnterpriseBackupNode_AlphaCentauriProtocol_EncryptedWorkflowRepository_VersionControlMaster_AdaptiveLearningEngine_IntegratedCl/jobs.json";

  /* ── HTML helpers ───────────────────────────────────────────────────── */
  function escAttr(s) {
    if (s == null) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function escHtml(s) {
    if (s == null) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  /* ── Location helpers ───────────────────────────────────────────────── */
  var REGION_MAP = {
    "Helsinki": "Uusimaa", "Espoo": "Uusimaa", "Vantaa": "Uusimaa",
    "Kauniainen": "Uusimaa", "Kerava": "Uusimaa", "Järvenpää": "Uusimaa",
    "Hyvinkää": "Uusimaa", "Nurmijärvi": "Uusimaa", "Tuusula": "Uusimaa",
    "Tampere": "Pirkanmaa", "Nokia": "Pirkanmaa", "Ylöjärvi": "Pirkanmaa",
    "Turku": "Southwest Finland", "Salo": "Southwest Finland", "Raisio": "Southwest Finland",
    "Oulu": "North Ostrobothnia", "Lahti": "Paijat-Hame",
    "Kuopio": "North Savo", "Joensuu": "North Karelia",
    "Jyväskylä": "Central Finland", "Jyvaskyla": "Central Finland",
    "Pori": "Satakunta", "Rovaniemi": "Lapland",
    "Vaasa": "Ostrobothnia", "Seinäjoki": "South Ostrobothnia",
    "Lappeenranta": "South Karelia", "Kotka": "Kymenlaakso",
    "Kouvola": "Kymenlaakso", "Hämeenlinna": "Tavastia Proper",
    "Mikkeli": "South Savo", "Kajaani": "Kainuu",
    "Kontiolahti": "North Karelia", "Lapua": "South Ostrobothnia"
  };

  function buildLocationText(job) {
    var city = (job.jobLocation || [])[0] || "";
    if (!city) return "";
    var region = REGION_MAP[city] || "";
    return region ? (city + ", " + region + ", Finland") : (city + ", Finland");
  }

  function buildLocationSlug(job) {
    var city = (job.jobLocation || [])[0] || "";
    return city.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  }

  /* ── Misc helpers ───────────────────────────────────────────────────── */
  function cap(w) { return w ? w.charAt(0).toUpperCase() + w.slice(1) : w; }

  function categoryLabel(slug) {
    if (!slug) return "Other";
    return slug.split(/[-_]/).map(cap).join(" ");
  }

  function fmtDate(iso) {
    if (!iso) return "";
    try {
      var d = new Date(iso.substring(0, 10) + "T00:00:00");
      return d.toLocaleDateString("en-US", { month: "short", day: "2-digit", year: "numeric" });
    } catch (e) { return iso; }
  }

  function buildDataTitle(job) {
    var parts = [];
    if (job.title)          parts.push(job.title.toLowerCase());
    if (job.company)        parts.push(job.company.toLowerCase());
    (job.jobLocation || []).forEach(function (l) { if (l) parts.push(l.toLowerCase()); });
    if (job.job_category)   parts.push(job.job_category.toLowerCase().replace(/[-_]/g, " "));
    if (job.search_keywords) parts.push(job.search_keywords.toLowerCase());
    return escAttr(parts.join(" "));
  }

  /* ── Bookmark SVG (identical to generator output) ───────────────────── */
  var BM_SVG =
    '<svg class="line" viewbox="0 0 24 24">' +
      '<g transform="translate(4.500000, 2.500000)">' +
        '<path d="M7.47,0 C1.08,0 0,0.932 0,8.429 C0,16.822 -0.15,19 1.44,19 ' +
              'C3.04,19 5.64,15.316 7.47,15.316 C9.3,15.316 11.9,19 13.5,19 ' +
              'C15.09,19 14.94,16.822 14.94,8.429 C14.94,0.932 13.86,0 7.47,0 Z"></path>' +
        '<line class="svgC v" transform="translate(-4.5,-2.5)" x1="12" x2="12" y1="6" y2="12"></line>' +
        '<line class="svgC h" transform="translate(-4.5,-2.5)" x1="15" x2="9" y1="9" y2="9"></line>' +
      '</g>' +
    '</svg>';

  /* ── Article card renderer ──────────────────────────────────────────── */
  function renderCard(job) {
    var jobUrl    = job.jobUrl || job.jobapply_link || "#";
    var imageUrl  = job.image_url || "https://findjobsinfinland.fi/images/jobs/other/1.png";
    var jobId     = job.job_id || job.id || "";
    var title     = job.title || "Untitled";
    var category  = job.job_category || "other";
    var locText   = buildLocationText(job);
    var locSlug   = buildLocationSlug(job);
    var published = job.date_posted || (job.scraped_at || "").substring(0, 10);
    var workTime  = (job.workTime || "full-time").toLowerCase();
    var continuity = (job.continuityOfWork || "permanent").toLowerCase();
    var langs     = (job.language_requirements || []).map(function (l) {
      return l.trim();
    }).join(" ");

    var snippet = job.meta_description || job.description || "";
    if (snippet.length > 220) snippet = snippet.substring(0, 220) + "\u2026";

    var posted = fmtDate(published);

    return (
      '<article class="ntry"' +
        ' data-category="' + escAttr(category) + '"' +
        ' data-continuityofwork="' + escAttr(continuity) + '"' +
        ' data-language="' + escAttr(langs) + '"' +
        ' data-location="' + escAttr(locSlug) + '"' +
        ' data-published="' + escAttr(published) + '"' +
        ' data-time="' + escAttr(workTime) + '"' +
        ' data-title="' + buildDataTitle(job) + '">' +

        '<div class="pThmb iyt">' +
          '<a class="thmb" href="' + escAttr(jobUrl) + '">' +
            '<img alt="' + escAttr(title) + '" class="imgThm lazy" data-src="' + escAttr(imageUrl) + '" src="' + escAttr(imageUrl) + '"/>' +
            '<noscript>' +
              '<img alt="' + escAttr(title) + '" class="imgThm" src="' + escAttr(imageUrl) + '"/>' +
            '</noscript>' +
          '</a>' +
          '<div class="iFxd" style="z-index:1;">' +
            '<span aria-label="Add to favorites"' +
              ' bm-id="' + escAttr(jobId) + '"' +
              ' bm-img="' + escAttr(imageUrl) + '"' +
              ' bm-ttl="' + escAttr(title + (locText ? " - " + locText : "")) + '"' +
              ' bm-url="' + escAttr(jobUrl) + '"' +
              ' class="bM bmPs" role="button">' +
              BM_SVG +
            '</span>' +
          '</div>' +
        '</div>' +

        '<div class="pCntn">' +
          '<div class="pHdr pSml">' +
            '<div class="pLbls" data-text="In" style="font-weight:bold;">' +
              '<a data-text="' + escAttr(locText) + '" rel="tag"' +
                ' style="pointer-events:none;color:inherit;text-decoration:none;"></a>' +
            '</div>' +
          '</div>' +
          '<h2 class="pTtl aTtl sml h1font">' +
            '<a data-text="' + escAttr(title) + '" href="' + escAttr(jobUrl) + '" rel="bookmark">' +
              escHtml(title) +
            '</a>' +
          '</h2>' +
          '<div class="pSnpt">' +
            escHtml(snippet) +
            '<div class="pInf pSml" style="color:red;font-weight:bold;">' +
              '<time class="aTtmp pTtmp pbl"' +
                ' datetime="' + escAttr(published) + '"' +
                ' title="Posted: ' + escAttr(posted) + '">' +
                escHtml(posted) +
              '</time>' +
              '<a class="pJmp" href="' + escAttr(jobUrl) + '">Apply Now</a>' +
            '</div>' +
          '</div>' +
        '</div>' +
      '</article>'
    );
  }

  /* ── Flatten grouped sessions → flat sorted array ───────────────────── */
  function flattenJobs(data) {
    var flat = [];
    if (!Array.isArray(data)) return flat;
    data.forEach(function (session) {
      var jobs = Array.isArray(session.jobs) ? session.jobs :
                 Array.isArray(session)      ? session      : [];
      jobs.forEach(function (j) { flat.push(j); });
    });
    // Newest first
    flat.sort(function (a, b) {
      var da = (a.date_posted || (a.scraped_at || "")).substring(0, 10);
      var db = (b.date_posted || (b.scraped_at || "")).substring(0, 10);
      return da < db ? 1 : da > db ? -1 : 0;
    });
    return flat;
  }

  /* ── Populate Category & Location dropdowns from actual data ─────────── */
  function populateDropdowns(jobs) {
    var catMenu = document.getElementById("categoryDropdownMenu");
    var locMenu = document.getElementById("locationDropdownMenu");
    var catSet  = {};
    var locSet  = {};

    jobs.forEach(function (j) {
      if (j.job_category) catSet[j.job_category] = true;
      (j.jobLocation || []).forEach(function (l) { if (l) locSet[l.trim()] = true; });
    });

    function rebuildMenu(menu, items, labelFn, slugFn) {
      if (!menu) return;
      var searchW = menu.querySelector(".search-wrapper");
      menu.innerHTML = "";
      if (searchW) menu.appendChild(searchW);

      var allDiv = document.createElement("div");
      allDiv.dataset.value = "";
      allDiv.textContent = menu === catMenu ? "All Categories" : "All Locations";
      menu.appendChild(allDiv);

      Object.keys(items).sort().forEach(function (key) {
        var d = document.createElement("div");
        d.dataset.value = slugFn ? slugFn(key) : key;
        d.textContent   = labelFn(key);
        menu.appendChild(d);
      });
    }

    rebuildMenu(catMenu, catSet, categoryLabel, null);
    rebuildMenu(locMenu, locSet,
      function (l) { return l; },
      function (l) { return l.toLowerCase().replace(/[^a-z0-9]+/g, "-"); }
    );
  }

  /* ── Kick the existing filter + view scripts ─────────────────────────── */
  function kickExistingScripts() {
    /* The filter script sets up on DOMContentLoaded and reads all articles.
       After we inject new articles we need to re-trigger it.
       It exposes filterArticles() as a local var inside its IIFE but we can
       dispatch a synthetic event it listens on, or just call it if it got
       attached to window in some builds. */
    if (typeof window.filterArticles === "function") {
      window.filterArticles();
    }

    /* View-toggle: applyView is an inner function. Re-fire DOMContentLoaded
       substitute by dispatching our custom event. The existing view-toggle
       IIFE listens to DOMContentLoaded; since that already fired we rely on
       its internal applyView call being bound in the click listeners.
       Force a re-apply via localStorage key. */
    var savedMode;
    try { savedMode = localStorage.getItem("jobsViewMode") || "grid"; } catch (e) { savedMode = "grid"; }
    var blogPts = document.querySelector("#Blog1 .blogPts");
    if (blogPts) {
      if (savedMode === "list") blogPts.classList.add("list-view");
      else                      blogPts.classList.remove("list-view");
      blogPts.classList.add("view-ready");
    }

    /* Sync button active state */
    var gridBtn = document.getElementById("viewGridBtn");
    var listBtn = document.getElementById("viewListBtn");
    if (gridBtn) gridBtn.classList.toggle("active", savedMode !== "list");
    if (listBtn) listBtn.classList.toggle("active", savedMode === "list");
  }

  /* ── Main entry ─────────────────────────────────────────────────────── */
  function loadJobs() {
    var container = document.querySelector("#Blog1 .blogPts");
    if (!container) return;

    container.innerHTML =
      '<div style="text-align:center;padding:50px 20px;opacity:0.55;">' +
        '<svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor"' +
            ' stroke-width="2" style="animation:spin 1s linear infinite;">' +
          '<circle cx="12" cy="12" r="10" stroke-dasharray="31.4" stroke-dashoffset="10"/>' +
        '</svg>' +
        '<style>@keyframes spin{to{transform:rotate(360deg)}}</style>' +
        '<p style="margin-top:12px;">Loading jobs&hellip;</p>' +
      '</div>';

    fetch(JOBS_JSON_URL, { cache: "no-cache" })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status + " — " + JOBS_JSON_URL);
        return r.json();
      })
      .then(function (data) {
        var jobs = flattenJobs(data);

        /* Store all jobs globally so pagination can access them */
        window._allJobs = jobs;

        /* Update the "X job opportunities" badge */
        var countEl = document.getElementById("totalJobsCount");
        if (countEl) countEl.textContent = jobs.length.toLocaleString();

        /* Render ALL cards initially (pagination will hide/show via CSS) */
        container.innerHTML = jobs.map(renderCard).join("\n");

        /* Rebuild filter dropdowns with real categories / locations */
        populateDropdowns(jobs);

        /* Re-apply filters, view mode, and URL params */
        kickExistingScripts();

        /* Signal for any other listeners (pagination init listens here) */
        document.dispatchEvent(new CustomEvent("jobs-loaded", { detail: { count: jobs.length } }));
      })
      .catch(function (err) {
        container.innerHTML =
          '<div style="text-align:center;padding:40px;color:#e55;">' +
            '<strong>Could not load job listings.</strong><br>' +
            'Make sure the data file is accessible.<br>' +
            '<small style="opacity:0.6;">' + escHtml(String(err)) + '</small>' +
          '</div>';
        console.error("[jobs-loader]", err);
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", loadJobs);
  } else {
    loadJobs();
  }
})();
