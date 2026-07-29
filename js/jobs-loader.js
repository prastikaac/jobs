/**
 * jobs-loader.js  — Performance-optimised edition
 *
 * Key changes vs the old version:
 *  1. Renders ONLY the visible page's cards into the DOM (virtual pagination).
 *     Instead of dumping every article at once we keep all job data in
 *     window._allJobs (JS array) and only push the slice the user is looking
 *     at into #Blog1 .blogPts.
 *  2. Filtering works entirely against the JS array, not the live DOM.
 *  3. Uses { cache: "force-cache" } so the browser can serve from disk on
 *     repeat visits without an extra network round-trip.
 *  4. Debounces search-input filtering to avoid re-renders while the user
 *     is still typing.
 *
 * Public surface (unchanged):
 *   window._allJobs          – raw job array
 *   window.filterArticles()  – runs filter + re-renders current page slice
 *   event "jobs-loaded"      – dispatched after first render
 */
(function () {
  "use strict";

  /* ── Config ─────────────────────────────────────────────────────────── */
  var JOBS_JSON_URL = "xQ7mPfL92aKdR8vTnW3sYhU6cZe1BjFoP4rNxLmQa8VtHyC2dKsJwE9uGbRfXpLoM5qZaNcV7tHyD3kWsPbXeR8mQvT1uJnFyL6cKdSaP9wEr/pfbID9xRtQw7LmNzE4vHyK2sDaFc8PqW1uJmXoT5rVeYbCnL6kHsAzG3dRfUpQoXnT8vLmKeP2sHyW7cDaJfR9uGbNxQ4tVeMzLpKoY1xCfHsRw8nTaVqZdE6mPyUi.json";

  /* ── Shared render-state ─────────────────────────────────────────────── */
  var _currentPage   = 1;
  var _perPage       = 50;       // synced with #perPageSelect
  var _filteredJobs  = [];       // subset of window._allJobs matching active filters
  var _activeFilters = {};       // cache of last filter values

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

  function normalize(str) {
    return (str || "").toString().toLowerCase().trim()
      .replace(/,/g, " ").replace(/\s+/g, " ");
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

  /* ── Article card renderer (data-only, no DOM touches) ──────────────── */
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
    var langs = (job.language_requirements || []).map(function (l) {
      return l.trim();
    }).join(" ");

    var snippet = job.meta_description || job.description || "";
    if (snippet.length > 220) snippet = snippet.substring(0, 220) + "\u2026";

    var posted = fmtDate(published);

    return (
      '<article class="ntry"' +
      ' data-category="'       + escAttr(category)   + '"' +
      ' data-continuityofwork="' + escAttr(continuity) + '"' +
      ' data-language="'       + escAttr(langs)       + '"' +
      ' data-location="'       + escAttr(locSlug)     + '"' +
      ' data-published="'      + escAttr(published)   + '"' +
      ' data-time="'           + escAttr(workTime)    + '"' +
      ' data-title="'          + buildDataTitle(job)  + '">' +

      '<div class="pThmb iyt">' +
      '<a class="thmb" href="' + escAttr(jobUrl) + '">' +
      '<img alt="' + escAttr(title) + '" class="imgThm lazy loaded" lazied="" data-src="' + escAttr(imageUrl) + '" src="' + escAttr(imageUrl) + '"/>' +
      '<noscript>' +
      '<img alt="' + escAttr(title) + '" class="imgThm" src="' + escAttr(imageUrl) + '"/>' +
      '</noscript>' +
      '</a>' +
      '<div class="iFxd" style="z-index:1;">' +
      '<span aria-label="Add to favorites"' +
      ' bm-id="'  + escAttr(jobId)   + '"' +
      ' bm-img="' + escAttr(imageUrl) + '"' +
      ' bm-ttl="' + escAttr(title + (locText ? " - " + locText : "")) + '"' +
      ' bm-url="' + escAttr(jobUrl)  + '"' +
      ' class="bM bmPs" role="button">' +
      BM_SVG +
      '</span>' +
      '</div>' +
      '</div>' +

      '<div class="pCntn">' +
      '<div class="pHdr pSml">' +
      '<div class="pLbls" data-text="In " style="font-weight:bold;">' +
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
      '</div>' +
      '<div class="pInf pSml">' +
      '<time class="aTtmp pTtmp pbl"' +
      ' datetime="' + escAttr(published) + '"' +
      ' title="Posted: ' + escAttr(posted) + '">' +
      escHtml(posted) +
      '</time>' +
      '<a class="pJmp" href="' + escAttr(jobUrl) + '">Apply Now</a>' +
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
        Array.isArray(session) ? session : [];
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

  /* ── Build a pre-computed search string for a job (used by JS filter) ── */
  function buildSearchString(job) {
    return normalize([
      job.title || "",
      job.company || "",
      job.job_category || "",
      (job.jobLocation || []).join(" "),
      job.workTime || "",
      (job.language_requirements || []).join(" "),
      job.continuityOfWork || "",
      job.search_keywords || "",
      job.meta_description || "",
      job.description || ""
    ].join(" "));
  }

  /* ── Apply filter entirely in JS (no DOM reads) ─────────────────────── */
  function applyFilter(filters) {
    var jobs = window._allJobs || [];
    if (!jobs.length) return [];

    var q         = normalize(filters.q || "");
    var cats      = (filters.category || "").split(",").map(normalize).filter(Boolean);
    var locs      = (filters.location || "").split(",").map(function(v){return v.trim();}).filter(Boolean);
    var times     = (filters.time || "").split(",").map(normalize).filter(Boolean);
    var langs     = (filters.language || "").split(",").map(normalize).filter(Boolean);
    var conts     = (filters.continuity || "").split(",").map(normalize).filter(Boolean);
    var published = (filters.published || "").split(",").map(normalize).filter(Boolean);

    var today     = new Date();
    var todayDay  = new Date(today.getFullYear(), today.getMonth(), today.getDate());

    return jobs.filter(function (job) {
      // Search query
      if (q) {
        if (!job._searchString) {
          job._searchString = buildSearchString(job);
        }
        if (!job._searchString.includes(q)) return false;
      }

      // Category
      if (cats.length) {
        var jobCat = normalize(job.job_category || "");
        if (!cats.some(function(c){ return jobCat.includes(c); })) return false;
      }

      // Location
      if (locs.length) {
        var locSlug   = buildLocationSlug(job);
        var locText   = normalize(buildLocationText(job));
        var locMatch  = locs.some(function(l) {
          var rawL = l;
          // region: prefix — match against region name in locText
          if (rawL.startsWith("region:")) {
            var rName = normalize(rawL.replace(/^region:/, ""));
            return locText.includes(rName);
          }
          // city: prefix — match city name against locText/locSlug
          if (rawL.startsWith("city:")) {
            var cName = normalize(rawL.replace(/^city:/, ""));
            return locText.includes(cName) || locSlug.includes(cName.replace(/\s+/g,"-"));
          }
          return locText.includes(normalize(rawL)) || locSlug.includes(normalize(rawL).replace(/\s+/g,"-"));
        });
        if (!locMatch) return false;
      }

      // Time (full-time / part-time)
      if (times.length) {
        var jTime = normalize(job.workTime || "");
        if (!times.some(function(t){ return jTime.includes(t); })) return false;
      }

      // Language
      if (langs.length) {
        var jLang = normalize((job.language_requirements || []).join(" "));
        if (!langs.some(function(l){ return jLang.includes(l); })) return false;
      }

      // Continuity
      if (conts.length) {
        var jCont = normalize(job.continuityOfWork || "");
        if (!conts.some(function(c){ return jCont.includes(c); })) return false;
      }

      // Published date
      if (published.length) {
        var dateStr = job.date_posted || (job.scraped_at || "").substring(0, 10);
        if (!dateStr) return false;
        var parts = dateStr.split("-");
        if (parts.length !== 3) return false;
        var postedDay = new Date(+parts[0], (+parts[1]) - 1, +parts[2]);
        if (isNaN(postedDay.getTime())) return false;
        var diffDays = Math.floor((todayDay - postedDay) / 86400000);

        var pubMatch = published.some(function(p) {
          if (p === "today")     return diffDays === 0;
          if (p === "yesterday") return diffDays === 1;
          if (p === "3d")        return diffDays >= 0 && diffDays <= 3;
          if (p === "7d")        return diffDays >= 0 && diffDays <= 7;
          if (p === "15d")       return diffDays >= 0 && diffDays <= 15;
          return true;
        });
        if (!pubMatch) return false;
      }

      return true;
    });
  }

  /* ── Read active filters from DOM elements ───────────────────────────── */
  function readFilters() {
    function val(id) {
      var el = document.getElementById(id);
      return el ? el.value : "";
    }
    var qEl = document.getElementById("searchIn");
    var qNw = document.querySelector(".job-search-container input");
    var q   = (qNw && qNw.value.trim()) || (qEl && qEl.value.trim()) || "";

    return {
      q:          q,
      category:   val("categorySelect"),
      location:   val("locationSelect"),
      published:  val("publishedSelect"),
      time:       val("timeSelect"),
      language:   val("languageSelect"),
      continuity: val("continuitySelect")
    };
  }

  /* ── Render a slice of jobs into the DOM container ──────────────────── */
  function renderSlice(container, jobs, start, end) {
    var slice = jobs.slice(start, end);
    container.innerHTML = slice.map(renderCard).join("\n");

    // Re-init bookmark system on newly inserted nodes if Pu is available
    if (typeof window.Pu === "object" && typeof window.Pu.bkm === "function") {
      try { window.Pu.bkm(container); } catch(e) {}
    }
  }

  /* ── Update job count summary text ──────────────────────────────────── */
  function updateJobSummary(totalCount, filteredCount, isFiltered) {
    var totalEl    = document.getElementById("totalJobsCount");
    var filteredEl = document.getElementById("filteredJobsCount");
    var defaultEl  = document.getElementById("defaultText");
    var filteredEl2 = document.getElementById("filteredText");

    if (totalEl)    totalEl.textContent    = totalCount.toLocaleString();
    if (filteredEl) filteredEl.textContent = filteredCount.toLocaleString();

    if (defaultEl && filteredEl2) {
      if (isFiltered) {
        defaultEl.style.display  = "none";
        filteredEl2.style.display = "block";
      } else {
        defaultEl.style.display  = "block";
        filteredEl2.style.display = "none";
      }
    }
  }

  /* ── Render "no results" state ────────────────────────────────────────── */
  function updateNoResults(container, filteredCount) {
    var msgEl = document.getElementById("noResultsMessage");
    if (!msgEl) return;

    if (filteredCount > 0) {
      msgEl.style.display = "none";
      container.style.display = "";
    } else {
      msgEl.style.display = "block";
      msgEl.innerHTML =
        '<div class="no-job-wrap">' +
        '<img src="https://findjobsinfinland.fi/images/no-jobs.png" alt="No jobs found" class="no-job-img">' +
        '</div>';
      container.style.display = "none";
    }
  }

  /* ── Core: filter + paginate + render ───────────────────────────────── */
  function filterArticles() {
    if (typeof window._allJobs === "undefined") return;

    var container = document.querySelector("#Blog1 .blogPts");
    if (!container) return;

    var filters = readFilters();
    _activeFilters  = filters;
    _filteredJobs   = applyFilter(filters);

    var total    = (window._allJobs || []).length;
    var filtered = _filteredJobs.length;

    var isFiltered = Boolean(
      filters.q || filters.category || filters.location ||
      filters.published || filters.time || filters.language || filters.continuity
    );

    updateJobSummary(total, filtered, isFiltered);
    updateNoResults(container, filtered);

    // Signal pagination layer (if patched) to rebuild
    if (typeof window._paginationRebuild === "function") {
      window._paginationRebuild(_filteredJobs);
    } else {
      // Fallback: render first page directly
      var start = (_currentPage - 1) * _perPage;
      renderSlice(container, _filteredJobs, start, start + _perPage);
    }

    // Sync dropdowns
    syncDropdownUI(filters);
    renderFilterTags(filters);
    updateFilterButtonBackground(filters);
    updateURL(filters);
  }

  /* ── Expose public API (overridden after jobs load in loadJobs .then()) ── */
  // Note: window.filterArticles is set inside loadJobs() after the fetch
  // succeeds, so it always runs after DOMContentLoaded handlers in jobs.html
  // that may temporarily set their own window.filterArticles.

  /* ── Dropdown UI sync helpers (kept minimal — filter.js may override) ── */
  function syncDropdownUI(filters) {
    updateDD("#categoryDropdown",   filters.category,   "All Categories");
    updateDD("#locationDropdown",   filters.location,   "All Locations");
    updateDD("#publishedDropdown",  filters.published,  "Any Published Date");
    updateDD("#timeDropdown",       filters.time,       "All Job Times");
    updateDD("#languageDropdown",   filters.language,   "All Languages");
    updateDD("#continuityDropdown", filters.continuity, "All Type");
  }

  function updateDD(selector, value, defaultText) {
    var dropdown = document.querySelector(selector);
    if (!dropdown) return;

    var safeValue = value || "";
    var selectedValues = safeValue ? safeValue.split(",").map(function(v){return v.trim();}).filter(Boolean) : [];

    var label = dropdown.querySelector(".dropdown-label");
    var menuOptions = dropdown.querySelectorAll(".dropdown-menu div[data-value]");

    if (label) {
      var labelText = defaultText;
      if (selectedValues.length > 0) {
        var texts = [];
        menuOptions.forEach(function(opt) {
          var optVal = opt.getAttribute("data-value") || "";
          if (selectedValues.indexOf(optVal) !== -1) {
            texts.push(opt.textContent.trim());
          }
        });
        if (texts.length) labelText = texts.join(", ");
      }
      label.textContent = labelText;
    }

    dropdown.classList.toggle("has-value", selectedValues.length > 0);

    menuOptions.forEach(function(opt) {
      var optVal = opt.getAttribute("data-value") || "";
      opt.classList.toggle("active", selectedValues.indexOf(optVal) !== -1);
    });
  }

  function renderFilterTags(filters) {
    var el = document.getElementById("selectedFilters");
    if (!el) return;
    el.innerHTML = "";

    function addTag(label, value, clearFn) {
      if (!value) return;
      var values = value.split(",").map(function(v){return v.trim();}).filter(Boolean);
      values.forEach(function(v) {
        var tag = document.createElement("span");
        tag.className = "filter-tag";
        var txt = document.createElement("span");
        // Strip city:/region: prefixes, replace hyphens with spaces, capitalise first letter
        var displayV = v.replace(/^(city:|region:)/i, "").replace(/-/g, " ");
        displayV = displayV ? displayV.charAt(0).toUpperCase() + displayV.slice(1) : displayV;
        txt.textContent = displayV;
        var btn = document.createElement("button");
        btn.type = "button";
        btn.textContent = "×";
        btn.setAttribute("aria-label", "Remove " + label + " filter");
        btn.onclick = function() { clearFn(v); };
        tag.appendChild(txt);
        tag.appendChild(btn);
        el.appendChild(tag);
      });
    }

    function clearSelect(id, v) {
      var sel = document.getElementById(id);
      if (!sel) return;
      var cur = sel.value.split(",").map(function(x){return x.trim();}).filter(Boolean);
      sel.value = cur.filter(function(x){return x !== v;}).join(",");
      filterArticles();
    }

    if (filters.q) {
      var tag = document.createElement("span");
      tag.className = "filter-tag";
      var txt = document.createElement("span");
      txt.textContent = filters.q;
      var btn = document.createElement("button");
      btn.type = "button"; btn.textContent = "×";
      btn.onclick = function() {
        var ni = document.querySelector(".job-search-container input");
        var oi = document.getElementById("searchIn");
        if (ni) ni.value = "";
        if (oi) oi.value = "";
        filterArticles();
      };
      tag.appendChild(txt); tag.appendChild(btn);
      el.appendChild(tag);
    }

    addTag("Category",  filters.category,   function(v){ clearSelect("categorySelect",  v); });
    addTag("Location",  filters.location,   function(v){ clearSelect("locationSelect",  v); });
    addTag("Published", filters.published,  function(v){ clearSelect("publishedSelect", v); });
    addTag("Time",      filters.time,       function(v){ clearSelect("timeSelect",       v); });
    addTag("Language",  filters.language,   function(v){ clearSelect("languageSelect",  v); });
    addTag("Type",      filters.continuity, function(v){ clearSelect("continuitySelect",v); });
  }

  function updateFilterButtonBackground(filters) {
    var btn = document.querySelector(".filter-button");
    if (!btn) return;
    var isActive = filters.q || filters.category || filters.location ||
                   filters.published || filters.time || filters.language || filters.continuity;
    btn.style.backgroundColor = isActive ? "rgb(69 78 87 / 10%)" : "";
  }

  function updateURL(filters) {
    var params = new URLSearchParams();
    if (filters.q)          params.set("q",          filters.q);
    if (filters.category)   params.set("category",   filters.category);
    if (filters.location)   params.set("location",   filters.location);
    if (filters.published)  params.set("published",  filters.published);
    if (filters.time)       params.set("time",       filters.time);
    if (filters.language)   params.set("language",   filters.language);
    if (filters.continuity) params.set("continuity", filters.continuity);

    // Preserve ?page= if pagination set it
    var existingPage = new URLSearchParams(window.location.search).get("page");
    if (existingPage && parseInt(existingPage, 10) > 1) params.set("page", existingPage);

    var qs  = params.toString();
    var newURL = window.location.pathname + (qs ? "?" + qs : "");
    window.history.replaceState({}, "", newURL);
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
        d.textContent = labelFn(key);
        menu.appendChild(d);
      });
    }

    rebuildMenu(catMenu, catSet, categoryLabel, null);
    rebuildMenu(locMenu, locSet,
      function (l) { return l; },
      function (l) { return l.toLowerCase().replace(/[^a-z0-9]+/g, "-"); }
    );
  }

  /* ── Kick the view-toggle script ─────────────────────────────────────── */
  function kickViewToggle() {
    var savedMode;
    try { savedMode = localStorage.getItem("jobsViewMode") || "grid"; } catch (e) { savedMode = "grid"; }
    var blogPts = document.querySelector("#Blog1 .blogPts");
    if (blogPts) {
      if (savedMode === "list") blogPts.classList.add("list-view");
      else blogPts.classList.remove("list-view");
      blogPts.classList.add("view-ready");
    }

    var gridBtn = document.getElementById("viewGridBtn");
    var listBtn = document.getElementById("viewListBtn");
    if (gridBtn) gridBtn.classList.toggle("active", savedMode !== "list");
    if (listBtn) listBtn.classList.toggle("active", savedMode === "list");
  }

  /* ── Pagination bridge ───────────────────────────────────────────────── */
  // The inline pagination IIFE in jobs.html wraps window.filterArticles after
  // this script runs. We provide _paginationRebuild as a hook so the pagination
  // layer can call renderSlice directly.
  window._renderJobSlice = function(jobs, start, end) {
    var container = document.querySelector("#Blog1 .blogPts");
    if (!container) return;
    renderSlice(container, jobs, start, end);
    kickViewToggle();
  };

  /* ── Main entry ─────────────────────────────────────────────────────── */
  function loadJobs() {
    var container = document.querySelector("#Blog1 .blogPts");
    if (!container) return;

    var statusEl = document.getElementById("jobsStatusMsg");
    if (statusEl) {
      statusEl.innerHTML =
        '<div class="loader-container" style="display:flex;flex-direction:column;align-items:center;justify-content:center;padding:50px 20px;">' +
        '<div class="loading">' +
        '<span></span><span></span><span></span><span></span><span></span>' +
        '</div>' +
        '<style>.loading{--speed-of-animation:0.9s;--gap:6px;--first-color:#4c86f9;--second-color:#49a84c;--third-color:#f6bb02;--fourth-color:#f6bb02;--fifth-color:#2196f3;display:flex;justify-content:center;align-items:center;width:100px;gap:6px;height:100px}.loading span{width:4px;height:50px;background:var(--first-color);animation:scale var(--speed-of-animation) ease-in-out infinite}.loading span:nth-child(2){background:var(--second-color);animation-delay:-.8s}.loading span:nth-child(3){background:var(--third-color);animation-delay:-.7s}.loading span:nth-child(4){background:var(--fourth-color);animation-delay:-.6s}.loading span:nth-child(5){background:var(--fifth-color);animation-delay:-.5s}@keyframes scale{0%,40%,100%{transform:scaleY(.05)}20%{transform:scaleY(1)}}</style>' +
        '</div>';
    }

    // Use no-cache so new jobs are always picked up (server returns 304 if unchanged)
    fetch(JOBS_JSON_URL, { cache: "no-cache" })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status + " — " + JOBS_JSON_URL);
        return r.json();
      })
      .then(function (data) {
        var jobs = flattenJobs(data);

        // Pre-compute search strings for every job once
        jobs.forEach(function(j) {
          j._searchString = buildSearchString(j);
        });

        /* Store all jobs globally */
        window._allJobs  = jobs;
        _filteredJobs    = jobs.slice(); // initially unfiltered

        /* Override window.filterArticles NOW (after DOMContentLoaded has fired
           and the inline filter script in jobs.html has run its own assignment) */
        window.filterArticles = filterArticles;

        /* Clear loader */
        if (statusEl) statusEl.innerHTML = "";

        /* Update badge */
        var countEl = document.getElementById("totalJobsCount");
        if (countEl) countEl.textContent = jobs.length.toLocaleString();

        /* Rebuild dropdown menus — DISABLED: jobs.html's loadCategories() /
           loadLocations() already populate both menus from their own JSON
           files and attach click listeners. Calling populateDropdowns() here
           would replace the menu innerHTML and destroy those listeners. */
        // populateDropdowns(jobs);

        /* Run initial filter (applies URL params) */
        filterArticles();

        /* Apply view mode (grid/list) */
        kickViewToggle();

        /* Signal pagination layer */
        document.dispatchEvent(new CustomEvent("jobs-loaded", { detail: { count: jobs.length } }));
      })
      .catch(function (err) {
        if (statusEl) {
          statusEl.innerHTML =
            '<div style="text-align:center;padding:40px;color:#e55;">' +
            '<strong>Could not load job listings.</strong>' +
            '</div>';
        }
        console.error("[jobs-loader]", err);
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", loadJobs);
  } else {
    loadJobs();
  }
})();
