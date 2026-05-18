/**
 * notification-popup.js
 * Only injects notification content into pre-built HTML containers.
 * HTML structure lives in index.html, CSS lives in css/notification-popup.css.
 */

(function () {
  'use strict';

  /* ─── Sample Notifications Data ─────────────────────────────────────── */
  const notifications = [
    {
      id: 1,
      image: '/images/notification.png',
      title: '🎉 New Jobs Added Today',
      shortDesc: '47 fresh job listings across IT, healthcare, and logistics.',
      fullDesc: 'We just added 47 new job listings across multiple industries in Finland! Categories include Information Technology, Healthcare, Logistics, Cleaning, and more. Many positions are open to non-EU citizens and do not require Finnish language skills. Browse now and apply before they fill up — new openings go live every day!',
      time: '2 min ago',
      date: 'May 18, 2026 · 5:08 PM',
      read: false,
    },
    {
      id: 2,
      image: '/images/notification.png',
      title: '⏰ Summer Jobs Deadline',
      shortDesc: 'Applications for summer positions close this Friday.',
      fullDesc: 'Reminder: Several popular summer job applications are closing this Friday, May 22nd. These include berry-picking roles in Lapland, hotel staff positions in Helsinki, and outdoor activity coordinators in Tampere. Make sure your profile is complete and your CV is up to date. Don\'t miss out on your chance to work this summer in Finland!',
      time: '1 hour ago',
      date: 'May 18, 2026 · 4:11 PM',
      read: false,
    },
    {
      id: 3,
      image: '/images/notification.png',
      title: '📞 Job Alert: Cleaning',
      shortDesc: 'A new cleaning job match was found in Helsinki.',
      fullDesc: 'Good news! Based on your browsing history, we found a new Cleaning & Facility Services job in Helsinki that may be a great fit. The role is part-time, 20 hrs/week, paying €13.50/hr. No Finnish required — the employer communicates in English. The position starts June 1st. Click to view the full listing and apply directly from our platform.',
      time: '3 hours ago',
      date: 'May 18, 2026 · 2:08 PM',
      read: false,
    },
  ];

  /* ─── State ──────────────────────────────────────────────────────────── */
  let isOpen = false;

  /* ─── DOM references (set in init) ───────────────────────────────────── */
  let overlayEl, popupEl, detailEl, listEl;

  /* ─── Inject notification items into #np-list ────────────────────────── */
  function populateNotifications() {
    listEl.innerHTML = '';

    notifications.forEach(n => {
      const item = document.createElement('div');
      item.className = 'np-item';
      if (!n.read) item.classList.add('np-unread');
      item.setAttribute('data-id', n.id);
      item.setAttribute('role', 'button');
      item.setAttribute('tabindex', '0');

      item.innerHTML = `
        <div class="np-img-wrap">
          <img src="${n.image}" alt="${n.title}" loading="lazy"/>
        </div>
        <div class="np-item-body">
          <p class="np-item-title">${n.title}</p>
          <p class="np-item-desc">${n.shortDesc}</p>
          <span class="np-item-time">${n.time}</span>
        </div>
        <span class="np-unread-dot"></span>
        <span class="np-item-arrow">›</span>
      `;

      item.addEventListener('click', () => openDetail(n));
      item.addEventListener('keydown', e => { if (e.key === 'Enter') openDetail(n); });
      listEl.appendChild(item);
    });
  }

  /* ─── Badge helpers ──────────────────────────────────────────────────── */
  function countUnread() {
    return notifications.filter(n => !n.read).length;
  }

  function updateBadges() {
    const unread = countUnread();

    const popupBadge = document.getElementById('np-badge');
    if (popupBadge) popupBadge.textContent = unread || notifications.length;

    const bellBadge = document.getElementById('np-bell-badge');
    if (bellBadge) {
      bellBadge.textContent = unread > 9 ? '9+' : unread;
      bellBadge.classList.toggle('np-hidden', unread === 0);
    }
  }

  /* ─── Open / Close ───────────────────────────────────────────────────── */
  function openPopup() {
    if (isOpen) { closeAll(); return; }
    isOpen = true;
    requestAnimationFrame(() => {
      popupEl.classList.add('np-visible');
    });
  }

  function closeDetail() {
    detailEl.classList.remove('np-visible');
    overlayEl.classList.remove('np-visible');
    requestAnimationFrame(() => {
      popupEl.classList.add('np-visible');
    });
  }

  function closeAll() {
    popupEl.classList.remove('np-visible');
    detailEl.classList.remove('np-visible');
    overlayEl.classList.remove('np-visible');
    isOpen = false;
  }

  function openDetail(n) {
    n.read = true;
    const itemEl = popupEl.querySelector(`.np-item[data-id="${n.id}"]`);
    if (itemEl) itemEl.classList.remove('np-unread');
    updateBadges();

    popupEl.classList.remove('np-visible');
    overlayEl.classList.add('np-visible');

    detailEl.querySelector('#nd-header-title').textContent = n.title;
    const imgEl = detailEl.querySelector('#nd-img');
    imgEl.src = n.image;
    imgEl.alt = n.title;
    detailEl.querySelector('#nd-title').textContent = n.title;
    detailEl.querySelector('#nd-date').textContent = n.date;
    detailEl.querySelector('#nd-full-desc').textContent = n.fullDesc;

    requestAnimationFrame(() => {
      detailEl.classList.add('np-visible');
    });
  }

  /* ─── Bind events to existing HTML containers ────────────────────────── */
  function bindEvents() {
    document.getElementById('np-close-btn').addEventListener('click', closeAll);
    overlayEl.addEventListener('click', closeAll);
    document.getElementById('nd-back-btn').addEventListener('click', closeDetail);
    document.getElementById('nd-close-btn').addEventListener('click', closeAll);

    popupEl.addEventListener('click', function (e) { e.stopPropagation(); });
    detailEl.addEventListener('click', function (e) { e.stopPropagation(); });
  }

  /* ─── Hook into the notification bell icon ───────────────────────────── */
  function hookTrigger() {
    const label = document.querySelector('li.isNotif.notif label.tNotif');
    if (!label) return;

    const li = document.querySelector('li.isNotif.notif');
    if (li) {
      const badge = document.createElement('span');
      badge.id = 'np-bell-badge';
      badge.className = 'np-bell-badge';
      li.appendChild(badge);
      updateBadges();
    }

    label.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      openPopup();
    });

    const checkbox = document.getElementById('offNotif');
    if (checkbox) {
      checkbox.addEventListener('change', function () {
        if (this.checked) openPopup();
        else closeAll();
      });
    }
  }

  /* ─── Global keyboard / click handlers ───────────────────────────────── */
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && isOpen) closeAll();
  });

  document.addEventListener('click', function (e) {
    if (!isOpen) return;
    const popupVisible = popupEl.classList.contains('np-visible');
    const detailVisible = detailEl.classList.contains('np-visible');
    if (popupVisible && !detailVisible && !popupEl.contains(e.target)) {
      closeAll();
    }
  });

  /* ─── Init ───────────────────────────────────────────────────────────── */
  function init() {
    overlayEl = document.getElementById('np-overlay');
    popupEl = document.getElementById('np-popup');
    detailEl = document.getElementById('np-detail');
    listEl = document.getElementById('np-list');

    if (!overlayEl || !popupEl || !detailEl || !listEl) return;

    populateNotifications();
    bindEvents();
    hookTrigger();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
