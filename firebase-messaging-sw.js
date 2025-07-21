importScripts('https://www.gstatic.com/firebasejs/10.12.2/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.12.2/firebase-messaging-compat.js');

firebase.initializeApp({
  apiKey:            "AIzaSyAstAXkwifJ-ukfZKSXiLG_l9iNwg4tPw4",
  authDomain:        "findjobsinfinland-3c061.firebaseapp.com",
  projectId:         "findjobsinfinland-3c061",
  storageBucket:     "findjobsinfinland-3c061.appspot.com",
  messagingSenderId: "575437446165",
  appId:             "1:575437446165:web:51922bc01fd291b09b821c"
});

const messaging = firebase.messaging();

// Ensure service worker takes control immediately
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', () => self.clients.claim());

messaging.onBackgroundMessage(async (payload) => {
  const clientsArr = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });

  // Check if any tab is visible (active)
  const isClientVisible = clientsArr.some(c => c.visibilityState === 'visible' || c.focused);

  if (isClientVisible) {
    // ✅ Don't show notification if any tab is focused or visible
    console.log("Notification skipped — active tab exists.");
    return;
  }

  const { title = 'New notification', body, icon } = payload.notification || {};
  const { imageUrl, jobLink = '/' } = payload.data || {};

  self.registration.showNotification(title, {
    body,
    icon: icon || '/images/icon.png',
    image: imageUrl || undefined,
    data: { url: jobLink }
  });
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(clientsArr => {
      for (const client of clientsArr) {
        if (client.url === event.notification.data.url && 'focus' in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) return clients.openWindow(event.notification.data.url);
    })
  );
});
