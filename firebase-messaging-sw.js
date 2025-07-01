// /firebase-messaging-sw.js
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

self.addEventListener('install', () => self.skipWaiting());   // activate immediately
self.addEventListener('activate', () => self.clients.claim()); // control open pages

messaging.onBackgroundMessage(payload => {
  const { title = 'New notification', body, icon } = payload.notification ?? {};
  const { imageUrl, jobLink = '/' } = payload.data ?? {};

  self.registration.showNotification(title, {
    body,
    icon: icon || '/images/icon.png',
    image: imageUrl ?? undefined,
    data: { url: jobLink }
  });
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true })
           .then(clientsArr => {
             for (const c of clientsArr)
               if (c.url === event.notification.data.url && 'focus' in c) return c.focus();
             if (clients.openWindow) return clients.openWindow(event.notification.data.url);
           })
  );
});
