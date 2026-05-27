/**
 * notification-popup.js
 * Sources:
 *   1. /data/system-notifications.json  → shown to ALL users (website updates, features, tips)
 *   2. /users/{uid}/pushAlerts          → shown only when logged in (personalised job alerts)
 *
 * HTML structure → index.html | CSS → css/notification-popup.css
 *
 * ARCHITECTURE NOTE:
 *   - setupUI() runs synchronously as soon as the DOM is ready.
 *     It attaches all click / keyboard handlers so the popup opens instantly.
 *   - loadData() runs asynchronously in the background (Firebase + fetch).
 *     A loading shimmer is shown in the list until data arrives.
 */

import { initializeApp, getApps } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import { getAuth, onAuthStateChanged } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";
import {
  getFirestore,
  collection,
  doc,
  getDoc,
  query,
  orderBy,
  limit,
  getDocs,
  updateDoc,
  deleteDoc,
} from "https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js";

/* ─── Firebase init ──────────────────────────────────────────────────────── */
const firebaseConfig = {
  apiKey: "AIzaSyAstAXkwifJ-ukfZKSXiLG_l9iNwg4tPw4",
  authDomain: "findjobsinfinland-3c061.firebaseapp.com",
  projectId: "findjobsinfinland-3c061",
  storageBucket: "findjobsinfinland-3c061.firebasestorage.app",
  messagingSenderId: "575437446165",
  appId: "1:575437446165:web:51922bc01fd291b09b821c",
};
const app = getApps().length ? getApps()[0] : initializeApp(firebaseConfig);
const auth = getAuth(app);
const db   = getFirestore(app);

/* ─── State ──────────────────────────────────────────────────────────────── */
let isOpen = false;
let notifications     = [];
let systemNotifications = [];
let dataLoaded        = false;   // true once the first fetch cycle completes
let urlSlugHandled    = false;   // true once we've tried to auto-open a ?notif= slug
let currentUserFullName = "";    // user's fullName from Firestore (for digest summaries)

/* ─── DOM refs (set in setupUI) ──────────────────────────────────────────── */
let overlayEl, popupEl, detailEl, listEl;

/* ─── LocalStorage keys ──────────────────────────────────────────────────── */
const LS_READ_KEY    = "np_sys_read";
const LS_DELETED_KEY = "np_sys_deleted";

/* ─── Time helpers ───────────────────────────────────────────────────────── */
function formatTimeAgo(ts) {
  if (!ts) return "";
  const date = ts.toDate ? ts.toDate() : new Date(ts);
  const diff = Math.floor((Date.now() - date.getTime()) / 1000);
  if (diff < 60)    return "Just now";
  if (diff < 3600)  return `${Math.floor(diff / 60)} min ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function formatFullDate(ts) {
  if (!ts) return "";
  const date = ts.toDate ? ts.toDate() : new Date(ts);
  return date.toLocaleString("en-US", {
    month: "short", day: "numeric", year: "numeric",
    hour: "numeric", minute: "2-digit", hour12: true,
  });
}

/* ─── Type badge helper ──────────────────────────────────────────────────── */
function typeBadge(type) {
  const map = {
    feature:   { label: "New Feature" },
    update:    { label: "Update" },
    tip:       { label: "Tip" },
    job_alert: { label: "Job Alert" },
  };
  const b = map[type] || { label: "Notification" };
  return { label: b.label };
}

/* ─── Delete SVG icon ────────────────────────────────────────────────────── */
const TRASH_SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-trash3" viewBox="0 0 16 16">
  <path d="M6.5 1h3a.5.5 0 0 1 .5.5v1H6v-1a.5.5 0 0 1 .5-.5M11 2.5v-1A1.5 1.5 0 0 0 9.5 0h-3A1.5 1.5 0 0 0 5 1.5v1H1.5a.5.5 0 0 0 0 1h.538l.853 10.66A2 2 0 0 0 4.885 16h6.23a2 2 0 0 0 1.994-1.84l.853-10.66h.538a.5.5 0 0 0 0-1zm1.958 1-.846 10.58a1 1 0 0 1-.997.92h-6.23a1 1 0 0 1-.997-.92L3.042 3.5zm-7.487 1a.5.5 0 0 1 .528.47l.5 8.5a.5.5 0 0 1-.998.06L5 5.03a.5.5 0 0 1 .47-.53Zm5.058 0a.5.5 0 0 1 .47.53l-.5 8.5a.5.5 0 1 1-.998-.06l.5-8.5a.5.5 0 0 1 .528-.47M8 4.5a.5.5 0 0 1 .5.5v8.5a.5.5 0 0 1-1 0V5a.5.5 0 0 1 .5-.5"/>
</svg>`;

/* ─── Loading shimmer (shown while data hasn't arrived yet) ──────────────── */
function showLoadingShimmer() {
  if (!listEl) return;
  listEl.innerHTML = `
    <div class="np-shimmer-wrap">
      ${[1,2,3].map(() => `
        <div class="np-shimmer-item">
          <div class="np-shimmer-img"></div>
          <div class="np-shimmer-body">
            <div class="np-shimmer-line np-shimmer-short"></div>
            <div class="np-shimmer-line np-shimmer-long"></div>
            <div class="np-shimmer-line np-shimmer-med"></div>
          </div>
        </div>`).join("")}
    </div>`;
}

/* ─── 1. Fetch system notifications from JSON ────────────────────────────── */
async function fetchSystemNotifications() {
  if (systemNotifications.length > 0) return systemNotifications;
  try {
    const res = await fetch("/data/system-notifications.json?_=" + Date.now());
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    const readSet    = JSON.parse(localStorage.getItem(LS_READ_KEY)    || "[]");
    const deletedSet = JSON.parse(localStorage.getItem(LS_DELETED_KEY) || "[]");
    systemNotifications = data
      .filter(n => !deletedSet.includes(n.id))
      .map(n => ({
        id: n.id,
        // For system notifications the JSON id IS the URL slug (e.g. sys-update-001)
        // This is the "default unique id" stored in JS / JSON for system notifications
        notifId: n.id,
        firestoreRef: null,
        source: "system",
        title: n.title,
        shortDesc: n.description,
        fullDesc: n.description,
        image: n.imageUrl || "/images/notification.png",
        jobLink: n.jobLink || "",
        time: formatTimeAgo(n.createdAt),
        date: formatFullDate(n.createdAt),
        read: readSet.includes(n.id),
        type: n.type || "update",
        sortKey: new Date(n.createdAt).getTime(),
      }));
  } catch (e) {
    console.warn("Could not load system-notifications.json:", e.message);
    systemNotifications = [];
  }
  return systemNotifications;
}

/* ─── 2. Fetch personal pushAlerts ──────────────────────────────────────── */
async function fetchPushAlerts(userId) {
  try {
    const q = query(
      collection(db, "users", userId, "pushAlerts"),
      orderBy("createdAt", "desc"),
      limit(50)
    );
    const snap = await getDocs(q);

    const FREQ_LABELS = {
      daily:   { period: "today",      title: "New Job Opportunities Today" },
      weekly:  { period: "this week",  title: "New Job Opportunities This Week" },
      monthly: { period: "this month", title: "New Job Opportunities This Month" },
    };

    // Separate digest summaries (isDigestSummary:true) from per-job docs
    const digestSummaries = [];  // { frequency, doc }
    const perJobDocs      = [];  // all other pushAlert docs

    for (const d of snap.docs) {
      const data = d.data();
      if (data.isDigestSummary) {
        digestSummaries.push({ frequency: data.frequency, data, ref: d.ref, id: d.id });
      } else {
        perJobDocs.push({ data, ref: d.ref, id: d.id });
      }
    }

    // Build result list — per-job docs always shown individually
    const result = perJobDocs.map(({ data, ref, id }) => {
      const rawNotifId  = data.notifId || id;
      const cleanNotifId = rawNotifId.replace(/^push_/, "");
      return {
        id,
        notifId: cleanNotifId,
        firestoreRef: ref,
        source: "personal",
        title: data.title || "New Job Alert",
        shortDesc: data.description || "",
        fullDesc:  data.description || "",
        image:    data.imageUrl || "/images/notification.png",
        jobLink:  data.jobLink  || "",
        time:  formatTimeAgo(data.createdAt),
        date:  formatFullDate(data.createdAt),
        read:  data.read === true,
        type:  "job_alert",
        sortKey: data.createdAt?.toMillis?.() || 0,
      };
    });

    // For each digest summary, inject a synthetic "summary" notification at the top.
    // The digest doc is also added as a regular card so clicking it shows the full description.
    for (const { frequency, data, ref, id } of digestSummaries) {
      const fl        = FREQ_LABELS[frequency] || { period: frequency, title: "New Job Opportunities" };
      const rawNotifId  = data.notifId || id;
      const cleanNotifId = rawNotifId.replace(/^digest_/, "").replace(/^push_/, "");
      const jobCount  = data.jobsCount || 0;
      const displayName = (currentUserFullName || "").trim() || "there";

      // Build the personalized summary message
      const summaryFullDesc =
        `Dear ${displayName},\n\n` +
        `We're pleased to inform you that ${jobCount} new job ${
          jobCount === 1 ? "opportunity" : "opportunities"
        } matching your preferences have been published ${fl.period}.\n\n` +
        `Explore the latest listings and discover roles that align with your career goals. ` +
        `You can view all new opportunities in the Notifications panel.`;

      const summaryShortDesc =
        `${jobCount} new job ${
          jobCount === 1 ? "opportunity" : "opportunities"
        } matching your preferences published ${fl.period}.`;

      const digestSortKey = (data.createdAt?.toMillis?.() || 0) + 1; // pin above per-job items

      // Synthetic summary card (uses same Firestore ref for mark-as-read/delete)
      result.push({
        id: `summary_${id}`,          // unique synthetic id so it doesn't clash
        notifId: `summary_${cleanNotifId}`,
        firestoreRef: ref,             // shares ref → deleting it removes the digest doc
        source: "personal",
        isDigestSummary: true,
        frequency,
        title: fl.title,
        shortDesc: summaryShortDesc,
        fullDesc:  summaryFullDesc,
        image: data.imageUrl || "/images/notification.png",
        jobLink: "",
        time:  formatTimeAgo(data.createdAt),
        date:  formatFullDate(data.createdAt),
        read:  data.read === true,
        type:  "job_alert",
        sortKey: digestSortKey,
      });
    }

    return result;
  } catch (e) {
    console.error("Failed to fetch pushAlerts:", e);
    return [];
  }
}

/* ─── Fetch user fullName from Firestore ─────────────────────────────────── */
async function fetchUserFullName(userId) {
  try {
    const userDoc = await getDoc(doc(db, "users", userId));
    if (userDoc.exists()) {
      const d = userDoc.data();
      currentUserFullName = (d.fullName || d.displayName || "").trim();
    }
  } catch (_) {
    // non-critical — fallback to empty string
  }
}

/* ─── Mark as read ───────────────────────────────────────────────────────── */
async function markAsRead(n) {
  if (n.read) return;
  n.read = true;
  if (n.source === "system") {
    const readSet = JSON.parse(localStorage.getItem(LS_READ_KEY) || "[]");
    if (!readSet.includes(n.id)) { readSet.push(n.id); localStorage.setItem(LS_READ_KEY, JSON.stringify(readSet)); }
    const cached = systemNotifications.find(s => s.id === n.id);
    if (cached) cached.read = true;
  } else if (n.firestoreRef) {
    try { await updateDoc(n.firestoreRef, { read: true }); } catch (_) { }
  }
}

/* ─── Delete a notification ──────────────────────────────────────────────── */
async function deleteNotification(n, itemEl) {
  itemEl.classList.add("np-item-deleting");
  await new Promise(resolve => {
    itemEl.addEventListener("animationend", resolve, { once: true });
    setTimeout(resolve, 450);
  });
  itemEl.remove();
  notifications = notifications.filter(x => x.id !== n.id);

  if (n.source === "system") {
    const deletedSet = JSON.parse(localStorage.getItem(LS_DELETED_KEY) || "[]");
    if (!deletedSet.includes(n.id)) { deletedSet.push(n.id); localStorage.setItem(LS_DELETED_KEY, JSON.stringify(deletedSet)); }
    const readSet = JSON.parse(localStorage.getItem(LS_READ_KEY) || "[]");
    localStorage.setItem(LS_READ_KEY, JSON.stringify(readSet.filter(id => id !== n.id)));
    systemNotifications = systemNotifications.filter(s => s.id !== n.id);
  } else if (n.firestoreRef) {
    try { await deleteDoc(n.firestoreRef); } catch (e) { console.error("Failed to delete from Firestore:", e); }
  }

  updateBadges();
  if (notifications.length === 0) { showEmptyState(); }
  else { const old = listEl.querySelector(".np-end-of-list"); if (old) old.remove(); appendEndOfList(); }
}

/* ─── Empty state ────────────────────────────────────────────────────────── */
function showEmptyState() {
  listEl.innerHTML = `
    <div class="np-empty">
      <img src="/images/no-notification.png" alt="No notifications" class="np-empty-img" onerror="this.style.display='none'"/>
      <p class="np-empty-title">No Notifications</p>
      <p class="np-empty-sub">You're all caught up! 🎉</p>
    </div>`;
}

/* ─── End-of-list block ──────────────────────────────────────────────────── */
function appendEndOfList() {
  const endEl = document.createElement("div");
  endEl.className = "np-end-of-list";
  endEl.innerHTML = `
    <span class="np-caught-up">You're all caught up.</span>
    <span class="np-expiry-note">Job alerts are automatically deleted after 3 days</span>
  `;
  listEl.appendChild(endEl);
}

/* ─── Merge ──────────────────────────────────────────────────────────────── */
function buildNotifications(sys, personal) {
  return [...sys, ...personal].sort((a, b) => b.sortKey - a.sortKey);
}

/* ─── Render ─────────────────────────────────────────────────────────────── */
function populateNotifications() {
  listEl.innerHTML = "";
  if (notifications.length === 0) { showEmptyState(); updateBadges(); return; }

  notifications.forEach(n => {
    const badge = typeBadge(n.type);
    const item = document.createElement("div");
    let cls = "np-item" + (n.read ? "" : " np-unread");
    if (n.isDigestSummary) cls += " np-digest-summary";
    item.className = cls;
    item.setAttribute("data-id", n.id);
    item.setAttribute("role", "button");
    item.setAttribute("tabindex", "0");
    item.innerHTML = `
      <div class="np-img-wrap">
        <img src="${n.image}" alt="${n.title}" loading="lazy" onerror="this.src='/images/notification.png'"/>
      </div>
      <div class="np-item-body">
        <span class="np-type-badge np-type-${n.type}">${badge.label}</span>
        <p class="np-item-title">${n.title}</p>
        <p class="np-item-desc">${n.shortDesc}</p>
        <span class="np-item-time">${n.time}</span>
      </div>
      <span class="np-unread-dot"></span>
      <button class="np-delete-btn" aria-label="Delete notification" title="Delete">${TRASH_SVG}</button>
    `;
    const body    = item.querySelector(".np-item-body");
    const imgWrap = item.querySelector(".np-img-wrap");
    [body, imgWrap].forEach(el => el.addEventListener("click", e => { e.stopPropagation(); openDetail(n); }));
    item.addEventListener("keydown", e => { if (e.key === "Enter") openDetail(n); });
    item.querySelector(".np-delete-btn").addEventListener("click", async e => { e.stopPropagation(); await deleteNotification(n, item); });
    listEl.appendChild(item);
  });

  appendEndOfList();
  updateBadges();
}


/* ─── Badges ─────────────────────────────────────────────────────────────── */
function countUnread() { return notifications.filter(n => !n.read).length; }

function updateBadges() {
  const unread = countUnread();
  const popupBadge = document.getElementById("np-badge");
  if (popupBadge) popupBadge.textContent = notifications.length;
  const bellBadge = document.getElementById("np-bell-badge");
  if (bellBadge) {
    bellBadge.textContent = unread > 9 ? "9+" : unread;
    bellBadge.classList.toggle("np-hidden", unread === 0);
  }
}

/* ─── URL slug helpers ───────────────────────────────────────────────────── */
function setUrlSlug(notifId) {
  const cleanId = (notifId || "").replace(/^push_/, "");
  const url = new URL(window.location.href);
  url.searchParams.set("notif", cleanId);
  window.history.replaceState(null, "", url.toString());
}

function clearUrlSlug() {
  const url = new URL(window.location.href);
  if (!url.searchParams.has("notif")) return;
  url.searchParams.delete("notif");
  // Use the bare path+search (removes trailing ? if no other params remain)
  const newUrl = url.pathname + (url.search === "?" ? "" : url.search);
  window.history.replaceState(null, "", newUrl);
}

/**
 * After data loads, check if the URL contains ?notif=<id>.
 * If found, auto-open the matching notification detail panel.
 * Only runs once per page load.
 */
async function handleUrlSlug() {
  if (urlSlugHandled) return;
  const params = new URLSearchParams(window.location.search);
  // params.get("notif") returns "" for ?notif= (empty), null if absent
  const slugParam = params.get("notif");
  if (slugParam === null) { urlSlugHandled = true; return; }  // no ?notif= at all

  // If ?notif= is empty, just open the panel and stop
  if (slugParam === "") {
    urlSlugHandled = true;
    if (!isOpen) {
      isOpen = true;
      if (!dataLoaded) showLoadingShimmer();
      requestAnimationFrame(() => popupEl.classList.add("np-visible"));
    }
    return;
  }

  const cleanSlug = slugParam.replace(/^push_/, "");

  // Clean up URL in the address bar immediately if it has the "push_" prefix
  if (slugParam !== cleanSlug) {
    const url = new URL(window.location.href);
    url.searchParams.set("notif", cleanSlug);
    window.history.replaceState(null, "", url.toString());
  }

  // Find the matching notification by its notifId (or id for system ones) with push_ prefix stripped
  const match = notifications.find(n => {
    const cleanId = (n.notifId || n.id || "").replace(/^push_/, "");
    return cleanId === cleanSlug;
  });
  if (!match) { urlSlugHandled = true; return; }

  urlSlugHandled = true;

  // Open the popup first (without toggling closed)
  if (!isOpen) {
    isOpen = true;
    if (!dataLoaded) showLoadingShimmer();
    popupEl.classList.add("np-visible");
  }
  // Small delay so popup renders before the detail slides in
  await new Promise(r => setTimeout(r, 80));
  openDetail(match);
}

/* ─── Open / Close ───────────────────────────────────────────────────────── */
function openPopup() {
  if (isOpen) { closeAll(); return; }
  isOpen = true;
  // Set ?notif= (empty) in the URL to indicate the panel is open
  const url = new URL(window.location.href);
  url.searchParams.set("notif", "");
  window.history.replaceState(null, "", url.toString());
  // If data hasn't loaded yet, show shimmer so the popup feels instant
  if (!dataLoaded) showLoadingShimmer();
  requestAnimationFrame(() => popupEl.classList.add("np-visible"));
}

function closeDetail() {
  // Go back to bare ?notif= (panel open, no specific notification selected)
  const url = new URL(window.location.href);
  url.searchParams.set("notif", "");
  window.history.replaceState(null, "", url.toString());
  detailEl.classList.remove("np-visible");
  overlayEl.classList.remove("np-visible");
  requestAnimationFrame(() => popupEl.classList.add("np-visible"));
}

function closeAll() {
  clearUrlSlug();
  popupEl.classList.remove("np-visible");
  detailEl.classList.remove("np-visible");
  overlayEl.classList.remove("np-visible");
  isOpen = false;
}

async function openDetail(n) {
  // Update URL slug so the notification can be shared / linked directly
  setUrlSlug(n.notifId || n.id);

  const itemEl = popupEl.querySelector(`.np-item[data-id="${n.id}"]`);
  if (itemEl) itemEl.classList.remove("np-unread");
  await markAsRead(n);
  updateBadges();

  popupEl.classList.remove("np-visible");
  overlayEl.classList.add("np-visible");

  const badge = typeBadge(n.type);
  detailEl.querySelector("#nd-header-title").textContent = n.title;
  const imgEl = detailEl.querySelector("#nd-img");
  imgEl.src = n.image; imgEl.alt = n.title;
  imgEl.onerror = () => { imgEl.src = "/images/notification.png"; };
  detailEl.querySelector("#nd-title").textContent = n.title;
  detailEl.querySelector("#nd-date").textContent = n.date;
  detailEl.querySelector("#nd-full-desc").textContent = n.fullDesc;

  let typeBadgeEl = detailEl.querySelector("#nd-type-badge");
  if (!typeBadgeEl) {
    typeBadgeEl = document.createElement("span");
    typeBadgeEl.id = "nd-type-badge";
    detailEl.querySelector("#nd-title").before(typeBadgeEl);
  }
  typeBadgeEl.className = `np-type-badge np-type-${n.type}`;
  typeBadgeEl.textContent = badge.label;

  const applyBtn = detailEl.querySelector("#nd-apply-btn");
  if (applyBtn) {
    if (n.jobLink) { applyBtn.href = n.jobLink; applyBtn.style.display = "flex"; }
    else { applyBtn.style.display = "none"; }
  }
  requestAnimationFrame(() => detailEl.classList.add("np-visible"));
}

/* ─── Bind events ────────────────────────────────────────────────────────── */
function bindEvents() {
  document.getElementById("np-close-btn").addEventListener("click", closeAll);
  overlayEl.addEventListener("click", closeAll);
  document.getElementById("nd-back-btn").addEventListener("click", closeDetail);
  document.getElementById("nd-close-btn").addEventListener("click", closeAll);
  popupEl.addEventListener("click", e => e.stopPropagation());
  detailEl.addEventListener("click", e => e.stopPropagation());
}

function hookTrigger() {
  const label = document.querySelector("li.isNotif.notif label.tNotif");
  if (!label) return;

  const li = document.querySelector("li.isNotif.notif");
  if (li && !document.getElementById("np-bell-badge")) {
    const badge = document.createElement("span");
    badge.id = "np-bell-badge";
    badge.className = "np-bell-badge np-hidden";
    li.appendChild(badge);
  }

  label.addEventListener("click", e => { e.preventDefault(); e.stopPropagation(); openPopup(); });

  const checkbox = document.getElementById("offNotif");
  if (checkbox) checkbox.addEventListener("change", function () {
    if (this.checked) openPopup(); else closeAll();
  });
}

/* ─── Keyboard / click-outside ───────────────────────────────────────────── */
document.addEventListener("keydown", e => { if (e.key === "Escape" && isOpen) closeAll(); });
document.addEventListener("click", e => {
  if (!isOpen) return;
  if (popupEl.classList.contains("np-visible") &&
    !detailEl.classList.contains("np-visible") &&
    !popupEl.contains(e.target)) closeAll();
});

/* ═══════════════════════════════════════════════════════════════════════════
   PHASE 1 — setupUI()
   Runs synchronously as soon as the DOM is ready.
   Attaches all event handlers so the popup opens instantly on click.
   No Firebase, no fetch — zero async delay.
   ═══════════════════════════════════════════════════════════════════════════ */
function setupUI() {
  overlayEl = document.getElementById("np-overlay");
  popupEl   = document.getElementById("np-popup");
  detailEl  = document.getElementById("np-detail");
  listEl    = document.getElementById("np-list");
  if (!overlayEl || !popupEl || !detailEl || !listEl) return false;

  showLoadingShimmer();   // pre-fill list so first open isn't blank
  bindEvents();
  hookTrigger();
  return true;
}

/* ═══════════════════════════════════════════════════════════════════════════
   PHASE 2 — loadData()
   Runs async in the background after UI is ready.
   Fetches system JSON + Firebase personal alerts, then re-renders the list.
   ═══════════════════════════════════════════════════════════════════════════ */
async function loadData() {
  const sys = await fetchSystemNotifications();
  notifications = buildNotifications(sys, []);
  dataLoaded = true;
  populateNotifications();
  // Check for ?notif= slug after first data load (system notifications only at this point)
  handleUrlSlug();

  onAuthStateChanged(auth, async user => {
    const sys = await fetchSystemNotifications();
    if (user) {
      // Fetch fullName first so digest summary cards are personalised
      await fetchUserFullName(user.uid);
      const personal = await fetchPushAlerts(user.uid);
      notifications = buildNotifications(sys, personal);
    } else {
      currentUserFullName = "";
      notifications = buildNotifications(sys, []);
    }
    dataLoaded = true;
    populateNotifications();
    // Re-check slug after personal alerts load — catches job-alert slugs for logged-in users
    urlSlugHandled = false;  // allow re-check now that personal alerts are available
    handleUrlSlug();
  });
}

/* ─── Bootstrap ──────────────────────────────────────────────────────────── */
function bootstrap() {
  if (setupUI()) loadData();   // fire-and-forget
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", bootstrap);
} else {
  bootstrap();
}
