/**
 * notification-popup.js
 * Sources:
 *   1. /data/system-notifications.json  → shown to ALL users (website updates, features, tips)
 *   2. /users/{uid}/pushAlerts          → shown only when logged in (personalised job alerts)
 *
 * HTML structure → index.html | CSS → css/notification-popup.css
 */

import { initializeApp, getApps } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import { getAuth, onAuthStateChanged } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";
import {
  getFirestore,
  collection,
  query,
  orderBy,
  limit,
  getDocs,
  updateDoc,
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
const db = getFirestore(app);

/* ─── State ──────────────────────────────────────────────────────────────── */
let isOpen = false;
let notifications = [];           // merged: system + personal
let systemNotifications = [];     // loaded once from JSON, cached

/* ─── DOM refs ───────────────────────────────────────────────────────────── */
let overlayEl, popupEl, detailEl, listEl;

/* ─── Time helpers ───────────────────────────────────────────────────────── */
function formatTimeAgo(ts) {
  if (!ts) return "";
  const date = ts.toDate ? ts.toDate() : new Date(ts);
  const diff = Math.floor((Date.now() - date.getTime()) / 1000);
  if (diff < 60) return "Just now";
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
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
    feature: { icon: "", label: "New Feature" },
    update: { icon: "", label: "Update" },
    tip: { icon: "", label: "Tip" },
    job_alert: { icon: "", label: "Job Alert" },
  };
  const b = map[type] || { icon: "", label: "Notification" };
  return { icon: b.icon, label: b.label, text: b.label };
}

/* ─── 1. Fetch system notifications from JSON (all users) ───────────────── */
async function fetchSystemNotifications() {
  if (systemNotifications.length > 0) return systemNotifications; // cached
  try {
    const res = await fetch("/data/system-notifications.json?_=" + Date.now());
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    // Read state persisted in localStorage so they aren't always "unread"
    const readSet = JSON.parse(localStorage.getItem("np_sys_read") || "[]");
    systemNotifications = data.map(n => ({
      id: n.id,
      firestoreRef: null,       // local — no Firestore ref
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

/* ─── 2. Fetch personal pushAlerts (logged-in users only) ───────────────── */
async function fetchPushAlerts(userId) {
  try {
    const q = query(
      collection(db, "users", userId, "pushAlerts"),
      orderBy("createdAt", "desc"),
      limit(20)
    );
    const snap = await getDocs(q);
    return snap.docs.map(d => ({
      id: d.id,
      firestoreRef: d.ref,
      source: "personal",
      title: d.data().title || "New Job Alert",
      shortDesc: d.data().description || "",
      fullDesc: d.data().description || "",
      image: d.data().imageUrl || "/images/notification.png",
      jobLink: d.data().jobLink || "",
      time: formatTimeAgo(d.data().createdAt),
      date: formatFullDate(d.data().createdAt),
      read: d.data().read === true,
      type: "job_alert",
      sortKey: d.data().createdAt?.toMillis?.() || 0,
    }));
  } catch (e) {
    console.error("Failed to fetch pushAlerts:", e);
    return [];
  }
}

/* ─── Mark as read ───────────────────────────────────────────────────────── */
async function markAsRead(n) {
  if (n.read) return;
  n.read = true;

  if (n.source === "system") {
    // Persist to localStorage
    const readSet = JSON.parse(localStorage.getItem("np_sys_read") || "[]");
    if (!readSet.includes(n.id)) {
      readSet.push(n.id);
      localStorage.setItem("np_sys_read", JSON.stringify(readSet));
    }
    // Sync to cached array
    const cached = systemNotifications.find(s => s.id === n.id);
    if (cached) cached.read = true;
  } else if (n.firestoreRef) {
    try { await updateDoc(n.firestoreRef, { read: true }); } catch (_) { }
  }
}

/* ─── Merge + render ─────────────────────────────────────────────────────── */
function buildNotifications(sys, personal) {
  // Merge all sources and sort globally by date — newest first
  return [...sys, ...personal].sort((a, b) => b.sortKey - a.sortKey);
}

function populateNotifications() {
  listEl.innerHTML = "";

  if (notifications.length === 0) {
    listEl.innerHTML = `
      <div class="np-empty">
        <svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"/>
        </svg>
        <p>No notifications yet</p>
      </div>`;
    updateBadges();
    return;
  }

  notifications.forEach(n => {
    const badge = typeBadge(n.type);
    const item = document.createElement("div");
    item.className = "np-item" + (n.read ? "" : " np-unread");
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
      <span class="np-item-arrow">›</span>
    `;

    item.addEventListener("click", () => openDetail(n));
    item.addEventListener("keydown", e => { if (e.key === "Enter") openDetail(n); });
    listEl.appendChild(item);
  });

  // End-of-list message after the last notification
  const endEl = document.createElement("div");
  endEl.className = "np-end-of-list";
  endEl.innerHTML = `
    <span class="np-caught-up">You're all caught up.</span>
    <span class="np-expiry-note">Job alerts are automatically deleted after 3 days</span>
  `;
  listEl.appendChild(endEl);

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

/* ─── Open / Close ───────────────────────────────────────────────────────── */
function openPopup() {
  if (isOpen) { closeAll(); return; }
  isOpen = true;
  requestAnimationFrame(() => popupEl.classList.add("np-visible"));
}

function closeDetail() {
  detailEl.classList.remove("np-visible");
  overlayEl.classList.remove("np-visible");
  requestAnimationFrame(() => popupEl.classList.add("np-visible"));
}

function closeAll() {
  popupEl.classList.remove("np-visible");
  detailEl.classList.remove("np-visible");
  overlayEl.classList.remove("np-visible");
  isOpen = false;
}

async function openDetail(n) {
  // Mark read
  const itemEl = popupEl.querySelector(`.np-item[data-id="${n.id}"]`);
  if (itemEl) itemEl.classList.remove("np-unread");
  await markAsRead(n);
  updateBadges();

  popupEl.classList.remove("np-visible");
  overlayEl.classList.add("np-visible");

  const badge = typeBadge(n.type);
  detailEl.querySelector("#nd-header-title").textContent = n.title;
  const imgEl = detailEl.querySelector("#nd-img");
  imgEl.src = n.image;
  imgEl.alt = n.title;
  imgEl.onerror = () => { imgEl.src = "/images/notification.png"; };
  detailEl.querySelector("#nd-title").textContent = n.title;
  detailEl.querySelector("#nd-date").textContent = n.date;
  detailEl.querySelector("#nd-full-desc").textContent = n.fullDesc;

  // Type badge in detail
  let typeBadgeEl = detailEl.querySelector("#nd-type-badge");
  if (!typeBadgeEl) {
    typeBadgeEl = document.createElement("span");
    typeBadgeEl.id = "nd-type-badge";
    detailEl.querySelector("#nd-title").before(typeBadgeEl);
  }
  typeBadgeEl.className = `np-type-badge np-type-${n.type}`;
  typeBadgeEl.textContent = `${badge.icon} ${badge.label}`;

  // Apply Now button
  const applyBtn = detailEl.querySelector("#nd-apply-btn");
  if (applyBtn) {
    if (n.jobLink) {
      applyBtn.href = n.jobLink;
      applyBtn.style.display = "flex";
    } else {
      applyBtn.style.display = "none";
    }
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

/* ─── Init ───────────────────────────────────────────────────────────────── */
async function init() {
  overlayEl = document.getElementById("np-overlay");
  popupEl = document.getElementById("np-popup");
  detailEl = document.getElementById("np-detail");
  listEl = document.getElementById("np-list");
  if (!overlayEl || !popupEl || !detailEl || !listEl) return;

  bindEvents();
  hookTrigger();

  // Load system notifications immediately for all visitors
  const sys = await fetchSystemNotifications();
  notifications = buildNotifications(sys, []);
  populateNotifications();

  // Load personal pushAlerts once authenticated
  onAuthStateChanged(auth, async user => {
    const sys = await fetchSystemNotifications();
    if (user) {
      const personal = await fetchPushAlerts(user.uid);
      notifications = buildNotifications(sys, personal);
    } else {
      notifications = buildNotifications(sys, []);
    }
    populateNotifications();
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
