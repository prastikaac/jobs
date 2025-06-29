// /public/firebase-messaging-sw.js
importScripts("https://www.gstatic.com/firebasejs/10.11.0/firebase-app-compat.js");
importScripts("https://www.gstatic.com/firebasejs/10.11.0/firebase-messaging-compat.js");

firebase.initializeApp({
    apiKey: "AIzaSyAstAXkwifJ-ukfZKSXiLG_l9iNwg4tPw4",
    authDomain: "findjobsinfinland-3c061.firebaseapp.com",
    projectId: "findjobsinfinland-3c061",
    storageBucket: "findjobsinfinland-3c061.firebasestorage.app",
    messagingSenderId: "575437446165",
    appId: "1:575437446165:web:51922bc01fd291b09b821c"
});

const messaging = firebase.messaging();

messaging.onBackgroundMessage(function (payload) {
    self.registration.showNotification(payload.notification.title, {
        body: payload.notification.body,
        icon: 'images/icon.png',
        data: { url: payload.notification.click_action }
    });
});

self.addEventListener("notificationclick", function (event) {
    event.notification.close();
    event.waitUntil(clients.openWindow(event.notification.data.url));
});
