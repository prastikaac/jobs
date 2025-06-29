// /js/firebase-push.js
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.11.0/firebase-app.js";
import { getAuth, onAuthStateChanged } from "https://www.gstatic.com/firebasejs/10.11.0/firebase-auth.js";
import { getFirestore, doc, updateDoc, arrayUnion } from "https://www.gstatic.com/firebasejs/10.11.0/firebase-firestore.js";
import { getMessaging, getToken, onMessage } from "https://www.gstatic.com/firebasejs/10.11.0/firebase-messaging.js";

const firebaseConfig = {
  apiKey: "AIzaSyAstAXkwifJ-ukfZKSXiLG_l9iNwg4tPw4",
  authDomain: "findjobsinfinland-3c061.firebaseapp.com",
  projectId: "findjobsinfinland-3c061",
  storageBucket: "findjobsinfinland-3c061.firebasestorage.app",
  messagingSenderId: "575437446165",
  appId: "1:575437446165:web:51922bc01fd291b09b821c"
};

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getFirestore(app);

let messaging;

async function initMessaging() {
  if ('serviceWorker' in navigator) {
    try {
      const registration = await navigator.serviceWorker.register('/firebase-messaging-sw.js');
      console.log('Service Worker registered:', registration);

      messaging = getMessaging(app);

    } catch (error) {
      console.error('Service Worker registration failed:', error);
    }
  } else {
    console.warn('Service Workers not supported in this browser.');
  }
}

initMessaging();

// Listen for auth state changes and enable push if user signed in
onAuthStateChanged(auth, (user) => {
  if (user) {
    // You can add UI enable button or automatically request permission here
    requestNotificationPermissionAndSaveToken(user);
  }
});

// Request permission and save token
async function requestNotificationPermissionAndSaveToken(user) {
  if (Notification.permission !== 'granted') {
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') {
      console.warn('Notification permission denied.');
      return;
    }
  }

  try {
    const token = await getToken(messaging, {
      vapidKey: "BMAg3rxpHjJdssyUfVzCcqrP-k89h_OtRzlmQ2OPPQQzoRrKhVeR73JMd6oZ91zO0J_Kx4K2avuIGIbF14RjWIY"
    });

    if (token) {
      console.log('FCM token:', token);
      const userRef = doc(db, "users", user.uid);
      await updateDoc(userRef, {
        fcmTokens: arrayUnion(token),
        email: user.email,
        fullName: user.displayName || ""
      });
    }
  } catch (error) {
    console.error('Error getting token:', error);
  }
}

// Handle foreground messages
onMessage(messaging, (payload) => {
  console.log('Message received:', payload);
  if (Notification.permission === 'granted') {
    const { title, body, icon } = payload.notification || {};
    const jobLink = payload.data?.jobLink || null;
    const imageUrl = payload.data?.imageUrl || null;

    const notification = new Notification(title || 'New Notification', {
      body: body || '',
      icon: icon || '/images/icon.png',
      image: imageUrl || undefined
    });

    notification.onclick = () => {
      if (jobLink && jobLink.startsWith('http')) {
        window.open(jobLink, '_blank');
      }
    };
  }
});
