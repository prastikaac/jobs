// /js/popupLogic.js

import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import {
  getFirestore, collection, query, where, getDocs, limit,
  doc, setDoc, getDoc, updateDoc, arrayUnion, arrayRemove, Timestamp, deleteField, addDoc
} from "https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js";
import {
  getAuth, createUserWithEmailAndPassword,
  signInWithEmailAndPassword, sendPasswordResetEmail
} from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";
import { onAuthStateChanged } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";
import { getMessaging, getToken, onMessage, deleteToken } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-messaging.js";






let ignoreNextOutsideClick = false;
let allowPopupClose = false;


const bc = new BroadcastChannel('notification-control');


const firebaseConfig = {
  apiKey: "AIzaSyAstAXkwifJ-ukfZKSXiLG_l9iNwg4tPw4",
  authDomain: "findjobsinfinland-3c061.firebaseapp.com",
  projectId: "findjobsinfinland-3c061",
  storageBucket: "findjobsinfinland-3c061.appspot.com",
  messagingSenderId: "575437446165",
  appId: "1:575437446165:web:51922bc01fd291b09b821c"
};

const app = initializeApp(firebaseConfig);
const db = getFirestore(app);
const auth = getAuth(app);











// ── Platform detection ──────────────────────────────────────────────────────
// Capacitor injects a custom User-Agent for both Android and iOS builds.
// We use this flag to skip web FCM logic inside the app — the app manages
// push notifications natively via MyFirebaseMessagingService + AppBridge.
const IS_IN_APP = /FindJobsFinlandApp/i.test(navigator.userAgent);

// ── Web FCM (browser users only) ─────────────────────────────────────────────
const LS_TOKEN_KEY = "currentFcmToken";
let messaging;
let _messagingInitPromise = null;
// Shared in-flight promise so concurrent callers never trigger two separate getToken() calls
let _tokenFetchPromise = null;

async function initMessaging() {
  if (IS_IN_APP) return null; // App handles FCM natively — skip entirely
  if (_messagingInitPromise) return _messagingInitPromise;
  _messagingInitPromise = (async () => {
    if (!("serviceWorker" in navigator)) return null;
    try {
      await navigator.serviceWorker.register("/firebase-messaging-sw.js", { scope: "/" });
      messaging = getMessaging(app);
      // Handle foreground messages (tab is open and visible)
      onMessage(messaging, (payload) => {
        if (Notification.permission !== "granted") return;
        const { title, body, icon } = payload.notification || {};
        const jobLink = payload.data?.jobLink || null;
        const imageUrl = payload.data?.imageUrl || null;
        const notif = new Notification(title || "New Job Alert", {
          body: body || "",
          icon: icon || "/images/icon.png",
          image: imageUrl || undefined
        });
        notif.onclick = () => {
          window.focus();
          if (jobLink && jobLink.startsWith("http")) window.open(jobLink, "_blank");
        };
      });
    } catch (e) {
      console.error("Messaging init failed:", e);
    }
    return messaging;
  })();
  return _messagingInitPromise;
}

async function getOrCreateFcmToken() {
  if (IS_IN_APP) return null;
  if (!("serviceWorker" in navigator && "PushManager" in window && "Notification" in window)) return null;
  if (!messaging) await initMessaging();
  if (!messaging) return null;
  if (Notification.permission !== "granted") return null;
  let registration;
  try { registration = await navigator.serviceWorker.ready; } catch (e) { return null; }

  // Return cached token immediately — no network call needed
  const cached = localStorage.getItem(LS_TOKEN_KEY);
  if (cached) return cached;

  // If another caller is already fetching, share its promise instead of making a second
  // getToken() call (which could return a different token before the cache is set).
  if (_tokenFetchPromise) return _tokenFetchPromise;

  _tokenFetchPromise = (async () => {
    try {
      const token = await getToken(messaging, {
        vapidKey: "BMAg3rxpHjJdssyUfVzCcqrP-k89h_OtRzlmQ2OPPQQzoRrKhVeR73JMd6oZ91zO0J_Kx4K2avuIGIbF14RjWIY",
        serviceWorkerRegistration: registration
      });
      if (token) localStorage.setItem(LS_TOKEN_KEY, token);
      return token || null;
    } catch (e) {
      console.error("getToken() failed:", e);
      return null;
    } finally {
      _tokenFetchPromise = null; // Allow a fresh attempt if this one failed
    }
  })();

  return _tokenFetchPromise;
}

// Save the current web FCM token to users/{uid}/fcmTokens in Firestore.
// Also removes any stale token that was previously cached in localStorage for this
// browser but has since changed (token rotation), preventing accumulation.
async function saveWebFcmToken(uid) {
  if (IS_IN_APP || !uid) return;
  // Gate check: only proceed if notifications are granted
  if (Notification.permission !== 'granted') return;
  try {
    // Read the previously cached token BEFORE fetching the current one.
    // If the token rotated, the cache is stale and we need to clean up Firestore.
    const previouslyCachedToken = localStorage.getItem(LS_TOKEN_KEY);

    const token = await getOrCreateFcmToken();
    if (!token) return;

    // If the token changed (rotation/fresh install), remove the stale Firestore entry.
    if (previouslyCachedToken && previouslyCachedToken !== token) {
      await updateDoc(doc(db, 'users', uid), { fcmTokens: arrayRemove(previouslyCachedToken) }).catch(() => {});
    }

    await updateDoc(doc(db, 'users', uid), { fcmTokens: arrayUnion(token) });
    console.log('Web FCM token saved.');
  } catch (e) {
    console.warn('Could not save web FCM token:', e);
  }
}

// Remove the current web FCM token from Firestore and delete it from FCM.
async function removeWebFcmToken(uid) {
  if (IS_IN_APP || !uid) return;
  const token = localStorage.getItem(LS_TOKEN_KEY);
  if (!token) return;
  try {
    await updateDoc(doc(db, "users", uid), { fcmTokens: arrayRemove(token) });
    if (messaging) { try { await deleteToken(messaging); } catch (_) {} }
    localStorage.removeItem(LS_TOKEN_KEY);
    console.log("Web FCM token removed.");
  } catch (e) {
    console.warn("Could not remove web FCM token:", e);
  }
}

// Initialize messaging on page load (browser only — no-op inside the app)
if (!IS_IN_APP) initMessaging();

const LS_SKIP_NO_CONFIRM = "skipNoConfirm";

let emailExists = false;

function showPopupStep(stepId) {
  const steps = [
    "popupStep1",              // Step 1: Job alert preference popup
    "popupStep1b",             // Step 1b: Re-enable notifications step
    "popupStep1c",             // Step 1c: Confirmation or next action
    "popupStep2",              // Other steps in your flow
    "popupStep3Signup1",       // Signup Step 1
    "popupStep3Signup2",       // Signup Step 2
    "popupStep3Login",         // Login Step
    "popupSignupSuccess",      // Success after signup
    "popupLoginSuccess",       // Success after login
    "popupBlockedNotifications", // Blocked Notifications (New Popup)
    "popupEnableNotifications"
  ];

  // Loop through all steps to show/hide them
  steps.forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.style.display = (id === stepId) ? "block" : "none";  // Show the stepId popup, hide others
    }
  });

  // Handle special popup display logic for the job alert container
  if (["popupStep1", "popupStep1b", "popupStep1c", "popupBlockedNotifications", "popupEnableNotifications"].includes(stepId)) {
    // Show the jobAlertPopup only for relevant steps
    if (document.getElementById("jobAlertPopup")) document.getElementById("jobAlertPopup").style.display = "flex";
  } else {
    // Hide the jobAlertPopup for other steps
    if (document.getElementById("jobAlertPopup")) document.getElementById("jobAlertPopup").style.display = "none";
  }
}



function closePopup() {
  // If browser supports notifications and permission is explicitly denied
  if ("Notification" in window && Notification.permission === "denied") {
    console.log("Notification permission denied. closePopup() will not execute.");
    return; // Stop here, don't hide the popup or set localStorage
  }

  // Otherwise, proceed to close the popup normally
  if (localStorage.getItem("neverShowJobAlertPopup") === "true") {
    localStorage.setItem("jobAlertPopupShown", "true");
  }

  if (document.getElementById("jobAlertPopup")) document.getElementById("jobAlertPopup").style.display = "none";
}


function validateEmail(email) {
  const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return re.test(email);
}

function validatePhone(phone) {
  const re = /^[0-9+\-() ]{6,20}$/;
  return re.test(phone);
}

function validatePassword(password) {
  return password.length >= 6;
}

function validateName(name) {
  return name.length > 0;
}

function getSelectedValues(containerId) {
  const container = document.getElementById(containerId);
  if (!container) return [];
  const checkboxes = container.querySelectorAll('input[type="checkbox"]:checked') || [];
  let selected = [];

  checkboxes.forEach(cb => {
    const val = cb.value.trim();
    if (val !== "" && val !== "all-categories" && val !== "all-location" && val !== "all-job-types" && val !== "all") {
      selected.push(val);
    }
  });

  return selected;
}

window.handlePopupYes = function () {
  // Open the popup container immediately — this starts the CSS open animation
  // right away so the user sees an instant response on click.
  // (clickLabelOnYes is no longer called separately from the onclick attribute.)
  window.clickLabelOnYes?.();

  function _showStep2() {
    showPopupStep("popupStep2");
    if (document.getElementById("jobAlertPopup")) document.getElementById("jobAlertPopup").style.display = "none";
    document.getElementById("profile-card-container").style.display = "block";
  }

  // Fast path: permission already decided (granted/denied) or we're in the app.
  // Show step 2 synchronously — no async delay whatsoever.
  if (IS_IN_APP || !("Notification" in window) || Notification.permission !== "default") {
    _showStep2();
    return;
  }

  // Slow path: permission is still "default" — ask the user.
  // The container is already opening (from clickLabelOnYes above), so the
  // browser dialog appears while the animation plays in the background.
  Notification.requestPermission()
    .catch(() => {})
    .finally(_showStep2);
};


window.handlePopupNo = () => {
  // Directly show the next step if "No" is pressed
  showPopupStep("popupStep1b"); // Or any other next step you want
};

window.handleNoSkipAlerts = () => {
  // This will show the confirmation step to skip alerts
  showPopupStep("popupStep1c");
};



window.confirmFinalNo = () => {
  const neverShowCheckbox = document.getElementById("neverShowAgainToggle");

  // If the checkbox is checked, set localStorage to remember it
  if (neverShowCheckbox && neverShowCheckbox.checked) {
    localStorage.setItem("neverShowJobAlertPopup", "true");
  } else {
    // If checkbox is not checked, set skipNoConfirm flag
    localStorage.setItem(LS_SKIP_NO_CONFIRM, "true");
  }

  // Close the popup regardless of the checkbox state
  closePopup();
};





window.checkEmailExistence = async () => {
  const emailInput = document.getElementById("popupEmail");
  const email = emailInput.value.trim();

  clearAllErrors();

  if (!validateEmail(email)) {
    showFieldError(emailInput, "Please enter a valid email address.");
    emailInput.focus();
    return;
  }

  // Validate required consent checkbox
  const consentJobAlerts = document.getElementById("consentJobAlerts");
  if (!consentJobAlerts || !consentJobAlerts.checked) {
    const consentErr = document.getElementById("consentJobAlertsError");
    if (consentErr) consentErr.textContent = "You must agree to continue.";
    return;
  }

  // Capture blog subscription preference (optional) for use in signupUser
  const consentBlogSubscribe = document.getElementById("consentBlogSubscribe");
  window._blogSubscriptionConsent = consentBlogSubscribe ? consentBlogSubscribe.checked : false;

  const q = query(collection(db, "users"), where("email", "==", email), limit(1));
  const querySnapshot = await getDocs(q);
  emailExists = !querySnapshot.empty;

  if (emailExists) {
    document.getElementById("popupEmailLogin").value = email;
    showPopupStep("popupStep3Login");
  } else {
    showPopupStep("popupStep3Signup1");
  }

  // **Hide the job alert popup immediately after email existence check**
  if (document.getElementById("jobAlertPopup")) document.getElementById("jobAlertPopup").style.display = "none";
  document.getElementById("profile-card-container").style.display = "block";
};




window.goToJobPreferenceStep = () => {
  clearAllErrors();

  const nameInput = document.getElementById("popupName");
  const phoneInput = document.getElementById("popupPhone");
  const emailInput = document.getElementById("popupEmail");
  const passInput = document.getElementById("popupPasswordNew");
  const confirmPassInput = document.getElementById("popupConfirmPassword");

  const name = nameInput.value.trim();
  const phone = phoneInput.value.trim();
  const email = emailInput.value.trim();
  const password = passInput.value;
  const confirmPassword = confirmPassInput.value;

  let hasError = false;

  if (!validateName(name)) {
    showFieldError(nameInput, "Please enter your full name.");
    nameInput.focus();
    hasError = true;
  }

  if (!validatePhone(phone)) {
    showFieldError(phoneInput, "Please enter a valid phone number.");
    if (!hasError) phoneInput.focus();
    hasError = true;
  }

  if (!validateEmail(email)) {
    showFieldError(emailInput, "Please enter a valid email address.");
    if (!hasError) emailInput.focus();
    hasError = true;
  }

  if (!validatePassword(password)) {
    showFieldError(passInput, "Password must be at least 6 characters.");
    if (!hasError) passInput.focus();
    hasError = true;
  }

  if (password !== confirmPassword) {
    showFieldError(confirmPassInput, "Passwords do not match.");
    if (!hasError) confirmPassInput.focus();
    hasError = true;
  }

  if (hasError) return;

  // **Hide the job alert popup immediately after validation passes**
  if (document.getElementById("jobAlertPopup")) document.getElementById("jobAlertPopup").style.display = "none";
  document.getElementById("profile-card-container").style.display = "block";

  // Go to next step after hiding the job alert popup
  showPopupStep("popupStep3Signup2");
};







// Updated showFieldError:
function showFieldError(inputElement, message) {
  const errorIdMap = {
    "popupName": "popupNameError",
    "popupPhone": "popupPhoneError",
    "popupPasswordNew": "popupPasswordError",
    "popupConfirmPassword": "popupConfirmPasswordError",
    "popupEmail": "popupEmailError",
    "popupPasswordLogin": "popupPasswordLoginError",
    "popupEmailLogin": "popupEmailLoginError"
  };

  // Find the error div by mapping input id
  const errorDivId = errorIdMap[inputElement.id];
  if (!errorDivId) {
    console.warn("No error div mapping for input:", inputElement.id);
    return;
  }
  const errorDiv = document.getElementById(errorDivId);
  if (errorDiv) {
    errorDiv.textContent = message;
  }
}

function clearAllErrors() {
  // Clear all existing known error divs by ID
  const errorDivs = [
    "popupNameError",
    "popupPhoneError",
    "popupPasswordError",
    "popupConfirmPasswordError",
    "popupEmailError",
    "consentJobAlertsError",
    "signupError",
    "categoryError",
    "locationError",
    "jobTimesError",
    "jobLangsError",
    "jobTypeError",
    "jobAlertSubError",
    "jobAlertFreqError"
  ];
  errorDivs.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.textContent = "";
  });
}

window.signupUser = async () => {
  const signupButton = document.getElementById("signupButton");  // Get the signup button
  signupButton.disabled = true;  // Disable the button after click

  clearAllErrors();

  const nameInput = document.getElementById("popupName");
  const phoneInput = document.getElementById("popupPhone");
  const emailInput = document.getElementById("popupEmail");
  const passInput = document.getElementById("popupPasswordNew");
  const confirmPassInput = document.getElementById("popupConfirmPassword");

  const name = nameInput.value.trim();
  const phone = phoneInput.value.trim();
  const email = emailInput.value.trim();
  const password = passInput.value;
  const confirmPassword = confirmPassInput.value;

  let hasError = false;

  // Validate fields
  if (!validateName(name)) {
    showFieldError(nameInput, "Please enter your full name.");
    nameInput.focus();
    hasError = true;
  }

  if (!validatePhone(phone)) {
    showFieldError(phoneInput, "Please enter a valid phone number.");
    if (!hasError) phoneInput.focus();
    hasError = true;
  }

  if (!validateEmail(email)) {
    showFieldError(emailInput, "Please enter a valid email address.");
    if (!hasError) emailInput.focus();
    hasError = true;
  }

  if (!validatePassword(password)) {
    showFieldError(passInput, "Password must be at least 6 characters.");
    if (!hasError) passInput.focus();
    hasError = true;
  }

  if (password !== confirmPassword) {
    showFieldError(confirmPassInput, "Passwords do not match.");
    if (!hasError) confirmPassInput.focus();
    hasError = true;
  }

  const jobCategory = getSelectedValues("categoryBox");
  const jobLocation = getSelectedValues("locationBox");

  if (jobCategory.length === 0) {
    const categoryError = document.getElementById("categoryError");
    if (categoryError) categoryError.textContent = "Please select at least one job category.";
    hasError = true;
  }

  if (jobLocation.length === 0) {
    const locationError = document.getElementById("locationError");
    if (locationError) locationError.textContent = "Please select at least one job location.";
    hasError = true;
  }

  const jobTimes = getSelectedValues("jobTimesBox");
  const jobLangs = getSelectedValues("jobLangsBox");
  const jobType = getSelectedValues("jobTypeBox");

  if (jobTimes.length === 0) {
    const err = document.getElementById("jobTimesError");
    if (err) err.textContent = "Please select at least one working time.";
    hasError = true;
  }

  if (jobLangs.length === 0) {
    const err = document.getElementById("jobLangsError");
    if (err) err.textContent = "Please select at least one working language.";
    hasError = true;
  }

  if (jobType.length === 0) {
    const err = document.getElementById("jobTypeError");
    if (err) err.textContent = "Please select at least one job type.";
    hasError = true;
  }

  const emailEnabled = document.getElementById("emailAlertToggle")?.checked ?? true;
  const pushEnabled = document.getElementById("pushAlertToggle")?.checked ?? true;

  const emailFreqEl = document.querySelector('input[name="emailFreq"]:checked');
  const emailAlertFrequency = emailFreqEl ? emailFreqEl.value : "daily";

  const pushFreqEl = document.querySelector('input[name="pushFreq"]:checked');
  const pushAlertFrequency = pushFreqEl ? pushFreqEl.value : "instantly";

  // Parse push schedule from the native time input
  const pushTimeVal = document.getElementById("pushScheduleTime")?.value || "09:00";
  const [pushHour, pushMinute] = pushTimeVal.split(":").map(Number);
  const pushDay = parseInt(document.getElementById("pushScheduleDay")?.value ?? "1", 10);
  const pushDate = parseInt(document.getElementById("pushScheduleDate")?.value ?? "1", 10);
  const pushScheduleTime = (pushAlertFrequency !== "instantly") ? {
    hour: isNaN(pushHour) ? 9 : pushHour,
    minute: isNaN(pushMinute) ? 0 : pushMinute,
    ...(pushAlertFrequency === "weekly" ? { dayOfWeek: pushDay } : {}),
    ...(pushAlertFrequency === "monthly" ? { dayOfMonth: pushDate } : {})
  } : null;

  // Parse email schedule from the native time input
  const emailTimeVal = document.getElementById("emailScheduleTime")?.value || "09:00";
  const [emailHour, emailMinute] = emailTimeVal.split(":").map(Number);
  const emailDay = parseInt(document.getElementById("emailScheduleDay")?.value ?? "1", 10);
  const emailDate = parseInt(document.getElementById("emailScheduleDate")?.value ?? "1", 10);
  const emailScheduleTime = {
    hour: isNaN(emailHour) ? 9 : emailHour,
    minute: isNaN(emailMinute) ? 0 : emailMinute,
    ...(emailAlertFrequency === "weekly" ? { dayOfWeek: emailDay } : {}),
    ...(emailAlertFrequency === "monthly" ? { dayOfMonth: emailDate } : {})
  };

  // Validate: at least one channel must be enabled
  if (!emailEnabled && !pushEnabled) {
    const err = document.getElementById("jobAlertSubError");
    if (err) err.textContent = "Please enable at least one notification channel.";
    hasError = true;
  }

  if (hasError) {
    signupButton.disabled = false;  // Re-enable the button in case of error
    // Scroll to the first error smoothly
    const firstError = document.querySelector('.error-message:not(:empty)');
    if (firstError) {
      firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    return;
  }

  // ── Show success popup INSTANTLY (optimistic UI) ───────────────────
  showPopupStep("popupSignupSuccess");

  try {
    // 1. Create the user in Firebase Auth
    const userCredential = await createUserWithEmailAndPassword(auth, email, password);
    const user = userCredential.user;

    const timestampNow = Timestamp.now();

    // 2. Store user details in Firestore with all requested fields
    await setDoc(doc(db, "users", user.uid), {
      uid: user.uid,
      email: user.email,
      phoneNumber: phone,
      fullName: name,
      jobCategory: jobCategory,
      jobLocation: jobLocation,
      jobTimes: jobTimes,
      jobLanguages: jobLangs,
      jobType: jobType,
      // Per-channel alert preferences
      emailAlertFrequency: emailAlertFrequency,
      emailScheduleTime: emailScheduleTime,
      pushAlertFrequency: pushAlertFrequency,
      pushScheduleTime: pushScheduleTime,
      // Legacy fallback: used by existing digest queries until migrated
      jobAlertFrequency: pushAlertFrequency,
      jobSubscription: {
        emailNotification: emailEnabled,
        pushNotification: pushEnabled,
      },
      // Blog subscription consent (set in Step 2)
      ...(window._blogSubscriptionConsent ? { BlogSubscriptionViaEmail: "yes" } : {}),
      createdAt: timestampNow,
      lastLogin: timestampNow,
      fcmTokens: [],  // Ensure this array is always created
      profilePictureUrl: ""  // 👈 default blank profile picture
    });


    // 3. Save to localStorage
    localStorage.setItem("user", JSON.stringify({
      uid: user.uid,
      email: user.email
    }));

    // 4. Register FCM token — only if user enabled push notifications
    if (pushEnabled) {
      if (IS_IN_APP && window.AppBridge) {
        try { window.AppBridge.onUserLoggedIn(user.uid); } catch (_) {}
      } else {
        saveWebFcmToken(user.uid).catch(() => {});
      }
    }

    // 5. Finalize - Show signup success popup
    showPopupStep("popupSignupSuccess");

    console.log("Signup completed for:", user.uid);

    // **Hide the signup success popup after 5 seconds, and unclick the label**
    setTimeout(() => {
      const commentSection = document.getElementById("comments");
      const fixedLabel = document.getElementById("neverhiddenpopup");

      if (commentSection) {
        commentSection.classList.add("hide-slide-down");
        commentSection.addEventListener("animationend", () => {
          commentSection.style.visibility = "hidden";
          commentSection.classList.remove("hide-slide-down");
        }, { once: true });
      }

      if (fixedLabel) {
        fixedLabel.classList.add("hide-slide-down");
        fixedLabel.addEventListener("animationend", () => {
          fixedLabel.style.visibility = "hidden";
          fixedLabel.classList.remove("hide-slide-down");
        }, { once: true });
      }

      // Keep popupSignupSuccess visible or handle separately
    }, 5000);



  } catch (error) {
    console.error("Signup error:", error);
    // Revert back to the preferences form on Firebase failure
    showPopupStep("popupStep3Signup2");
    const signupError = document.getElementById("signupPrefError");
    if (signupError) signupError.textContent = error.message || "Signup failed. Please try again.";

    // Re-enable the button in case of error
    signupButton.disabled = false;
  }
};



window.loginUser = async () => {
  const emailInput = document.getElementById("popupEmailLogin");
  const passInput = document.getElementById("popupPasswordLogin");

  const email = emailInput.value.trim();
  const password = passInput.value;

  let hasError = false;

  // Validate the email and password first
  if (!validateEmail(email)) {
    showFieldError(emailInput, "Please enter a valid email address.");
    emailInput.focus();
    hasError = true;
  }

  if (!validatePassword(password)) {
    showFieldError(passInput, "Please enter a valid password (min 6 chars).");
    passInput.focus();
    hasError = true;
  }

  if (hasError) return;

  try {
    // Attempt to sign in using Firebase Authentication
    const userCredential = await signInWithEmailAndPassword(auth, email, password);
    const user = userCredential.user;

    // Update lastLogin timestamp after successful login,
    // and set BlogSubscriptionViaEmail if the user opted in
    await updateDoc(doc(db, "users", user.uid), {
      lastLogin: Timestamp.now(),
      ...(window._blogSubscriptionConsent ? { BlogSubscriptionViaEmail: "yes" } : {})
    });


    console.log("Login successful! User:", user);

    // Now check the Firestore database for the user's additional details
    const userRef = doc(db, "users", user.uid);
    const docSnap = await getDoc(userRef);

    if (docSnap.exists()) {
      const userData = docSnap.data();
      console.log("User data retrieved from Firestore:", userData);

      // You can save this data to localStorage, or use it in your app
      localStorage.setItem("user", JSON.stringify({
        uid: user.uid,
        email: user.email,
        fullName: userData.fullName,
        phoneNumber: userData.phoneNumber,
        createdAt: userData.createdAt,
        lastLogin: Timestamp.now()

      }));

      // Optionally, you can show a success message and move to the next page
      showPopupStep("popupLoginSuccess");
      console.log("User logged in and data fetched successfully.");

      // Register FCM token — only if user has push notifications enabled
      if (userData?.jobSubscription?.pushNotification) {
        if (IS_IN_APP && window.AppBridge) {
          try { window.AppBridge.onUserLoggedIn(user.uid); } catch (_) {}
        } else {
          saveWebFcmToken(user.uid).catch(() => {});
        }
      }





      // First, unclick the <label> inside #logsinpop, then hide the popup after 5 seconds
      setTimeout(() => {
        const commentSection = document.getElementById("comments");
        const fixedLabel = document.getElementById("neverhiddenpopup");

        if (commentSection) {
          commentSection.classList.add("hide-slide-down");

          // After animation ends, set visibility to hidden (extra safety)
          commentSection.addEventListener("animationend", () => {
            commentSection.style.visibility = "hidden";
            commentSection.classList.remove("hide-slide-down");
          }, { once: true });
        }

        if (fixedLabel) {
          fixedLabel.classList.add("hide-slide-down");
          fixedLabel.addEventListener("animationend", () => {
            fixedLabel.style.visibility = "hidden";
            fixedLabel.classList.remove("hide-slide-down");
          }, { once: true });
        }

        // Note: Do not hide the success popup here if you want it to stay visible
      }, 5000);



    } else {
      console.log("No user data found in Firestore for the logged-in user.");
    }

  } catch (error) {
    console.error("Login failed:", error);
    // Revert back to the login form on Firebase failure
    showPopupStep("popupStep3Login");
    showFieldError(passInput, "Incorrect password. Please try again.");
  }
};


function hideSectionAndLabelWithAnimation(callback) {
  const commentSection = document.getElementById("comments");
  const fixedLabel = document.getElementById("neverhiddenpopup");

  let animCount = 0;
  const totalAnim = (commentSection ? 1 : 0) + (fixedLabel ? 1 : 0);

  function onAnimEnd() {
    animCount++;
    if (animCount === totalAnim) {
      callback();
    }
  }

  if (commentSection) {
    commentSection.classList.add("hide-slide-down");
    commentSection.addEventListener("animationend", () => {
      commentSection.style.visibility = "hidden";
      commentSection.classList.remove("hide-slide-down");
      onAnimEnd();
    }, { once: true });
  }

  if (fixedLabel) {
    fixedLabel.classList.add("hide-slide-down");
    fixedLabel.addEventListener("animationend", () => {
      fixedLabel.style.visibility = "hidden";
      fixedLabel.classList.remove("hide-slide-down");
      onAnimEnd();
    }, { once: true });
  }

  // If neither element exists, call callback immediately
  if (totalAnim === 0) {
    callback();
  }
}

function closeLoginPopup() {
  hideSectionAndLabelWithAnimation(() => {
    // Then unclick label and hide popup after animation finishes
    const loginLabel = document.getElementById('logsinpop')?.querySelector('label');
    if (loginLabel) {
      loginLabel.click();
    }

    const loginPopup = document.getElementById('popupLoginSuccess');
    if (loginPopup) {
      loginPopup.style.display = 'none';
    }
  });
}

function closeSignupPopup() {
  hideSectionAndLabelWithAnimation(() => {
    const signupLabel = document.getElementById('logsinpop')?.querySelector('label');
    if (signupLabel) {
      signupLabel.click();
    }

    const signupPopup = document.getElementById('popupSignupSuccess');
    if (signupPopup) {
      signupPopup.style.display = 'none';
    }
  });
}



// Wait for the DOM to be fully loaded before adding event listeners
document.addEventListener("DOMContentLoaded", function () {
  // Get the close button for login and attach event listener
  const closeLoginButton = document.getElementById('closeLoginPopupButton');
  if (closeLoginButton) {
    closeLoginButton.addEventListener('click', closeLoginPopup);
  }

  // Get the close button for signup and attach event listener
  const closeSignupButton = document.getElementById('closeSignupPopupButton');
  if (closeSignupButton) {
    closeSignupButton.addEventListener('click', closeSignupPopup);
  }
});

document.getElementById("logoffbtn")?.addEventListener("click", async () => {
  try {
    const currentUser = auth.currentUser;

    // 1. Remove FCM token on logout
    if (currentUser) {
      if (IS_IN_APP && window.AppBridge) {
        try { window.AppBridge.onUserLoggedOut(currentUser.uid); } catch (_) {}
      } else {
        await removeWebFcmToken(currentUser.uid);
      }
    }

    // 2. Clear user-related data from localStorage
    localStorage.removeItem("user");
    localStorage.removeItem("jobAlertPopupShown");
    localStorage.removeItem("LS_SKIP_NO_CONFIRM");
    localStorage.removeItem("neverShowJobAlertPopup"); // Reset so popup shows again for next user/session

    // 3. Logout the user from Firebase Authentication
    await auth.signOut();

    // 4. Reload the page to reflect logged-out state
    location.reload();

  } catch (error) {
    console.error("Logout failed:", error);
  }
});








window.addEventListener("load", () => {
  const neverShowPopup = localStorage.getItem("neverShowJobAlertPopup") === "true";

  onAuthStateChanged(auth, async (user) => {
    if (user) {
      // Logged in via Firebase — DO NOT show popupStep1
      // Also ensure localStorage is in sync
      if (!localStorage.getItem("user")) {
        localStorage.setItem("user", JSON.stringify({ uid: user.uid, email: user.email }));
      }
    } else {
      // Firebase definitively says user is NOT logged in.
      // Clear any stale localStorage user data so the rest of the page
      // (e.g., the blocked-notification DOMContentLoaded handler) doesn't
      // mistakenly think the user is logged in.
      localStorage.removeItem("user");

      // Only show popupStep1 if neverShowPopup is false
      if (!neverShowPopup) {
        if (!window.location.pathname.includes("edit-profile")) {
          setTimeout(() => {
            showPopupStep("popupStep1")
          }, 8000)
        }
      } else {
        closePopup()
      }
    }
  });
});








document.getElementById("forgotPasswordLink")?.addEventListener("click", async () => {
  const emailInput = document.getElementById("popupEmailLogin");
  const email = emailInput.value.trim();
  const messageDiv = document.getElementById("forgotPasswordMessage");

  // Clear previous message
  messageDiv.textContent = "";
  messageDiv.classList.remove("success", "error");
  clearAllErrors();

  if (!validateEmail(email)) {
    messageDiv.textContent = "Please enter a valid email address.";
    messageDiv.classList.add("error");
    emailInput.focus();
    return;
  }

  try {
    await sendPasswordResetEmail(auth, email);
    messageDiv.textContent = "A password reset link has been sent to your email address. Please check your inbox and follow the instructions to reset your password.";
    messageDiv.classList.add("success");
  } catch (error) {
    console.error("Password reset error:", error);
    messageDiv.textContent = "Failed to send reset email. Please check the address and try again.";
    messageDiv.classList.add("error");
  }

});





window.togglePassword = function (el) {
  const input = el.parentElement.querySelector('input[type="password"], input[type="text"]');
  if (input) {
    const isHidden = input.type === 'password';
    input.type = isHidden ? 'text' : 'password';
    el.textContent = isHidden ? 'Hide' : 'Show';
  }
};


window.clickLabelOnYes = function () {
  try {
    const label = document.getElementById('logsinpop')?.getElementsByTagName('label')[0];
    if (label) {
      label.click();
    } else {
      console.warn("Label element not found inside #logsinpop.");
    }
  } catch (e) {
    console.error("Error clicking label:", e);
  }
};









window.addEventListener("DOMContentLoaded", () => {
  // The blocked-notification popup is a web-only concern.
  // In the app, Android/iOS handles notification permission natively — skip entirely.
  if (IS_IN_APP) return;

  const skipNoConfirm = localStorage.getItem("LS_SKIP_NO_CONFIRM");
  const user = JSON.parse(localStorage.getItem("user"));

  // Both conditions must hold:
  //  1. User must be logged in (checked by login state, NOT notification state)
  //  2. Notification API must be available in this browser
  if (!("Notification" in window) || !user?.uid) return;

  setTimeout(() => {
    const permission = Notification.permission;

    // Only show the blocked popup if the user is logged in AND notification
    // permission has not been granted. This ensures the popup is NEVER shown
    // purely based on notification state — login state is the primary gate.
    if ((permission === "denied" || permission === "default") && skipNoConfirm !== "true") {
      const blockedPopup = document.getElementById("popupBlockedNotifications");

      if (blockedPopup) {
        if (document.getElementById("jobAlertPopup")) document.getElementById("jobAlertPopup").style.display = "flex";
        blockedPopup.style.display = "flex";
      }
    }
  }, 100); // Small delay gives the browser time to settle the permission state
});


document.getElementById("yesButtonBlockedNotifications")?.addEventListener("click", () => {
  localStorage.setItem("LS_SKIP_NO_CONFIRM", "true");
  document.getElementById("popupBlockedNotifications").style.display = "none";
  if (document.getElementById("jobAlertPopup")) document.getElementById("jobAlertPopup").style.display = "none";
});


document.getElementById("noButtonBlockedNotifications")?.addEventListener("click", async () => {
  const user = JSON.parse(localStorage.getItem("user"));

  // Inside the app, just close the popup — notifications are managed natively
  if (IS_IN_APP || !user?.uid) {
    document.getElementById("popupBlockedNotifications").style.display = "none";
    if (document.getElementById("jobAlertPopup")) document.getElementById("jobAlertPopup").style.display = "none";
    return;
  }

  const permission = Notification.permission;
  if (permission === "default") {
    try {
      const result = await Notification.requestPermission();
      if (result === "granted") {
        document.getElementById("popupBlockedNotifications").style.display = "none";
        if (document.getElementById("jobAlertPopup")) document.getElementById("jobAlertPopup").style.display = "none";
        await saveWebFcmToken(user.uid);
      } else {
        document.getElementById("popupBlockedNotifications").style.display = "none";
        document.getElementById("popupEnableNotifications").style.display = "flex";
        if (document.getElementById("jobAlertPopup")) document.getElementById("jobAlertPopup").style.display = "flex";
      }
    } catch (e) { console.error("Permission request failed:", e); }
  } else if (permission === "denied") {
    document.getElementById("popupBlockedNotifications").style.display = "none";
    document.getElementById("popupEnableNotifications").style.display = "flex";
    if (document.getElementById("jobAlertPopup")) document.getElementById("jobAlertPopup").style.display = "flex";
  } else {
    document.getElementById("popupBlockedNotifications").style.display = "none";
    if (document.getElementById("jobAlertPopup")) document.getElementById("jobAlertPopup").style.display = "none";
  }
});



document.querySelector(".blockclosebtn")?.addEventListener("click", () => {
  document.getElementById("popupEnableNotifications").style.display = "none";
  if (document.getElementById("jobAlertPopup")) document.getElementById("jobAlertPopup").style.display = "none";
});




document.addEventListener('click', function (e) {
  const popup = document.querySelector('.fixL');
  const checkbox = document.getElementById('forcontact');
  const isVisible = popup && window.getComputedStyle(popup).visibility === 'visible';

  // Allow hiding popup if triggered by success popup close
  if (allowPopupClose) {
    allowPopupClose = false;
    return; // Don't force checkbox checked
  }

  if (isVisible && !popup.contains(e.target)) {
    e.stopPropagation();
    checkbox.checked = true;
  }
});



document.addEventListener("DOMContentLoaded", function () {
  // Close buttons already handled...

  // ENTER KEY SUPPORT
  // 1. Enter on Email Check (popupStep2)
  const emailInput = document.getElementById("popupEmail");
  if (emailInput) {
    emailInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        window.checkEmailExistence();
      }
    });
  }

  // 2. Enter on Login Form (popupStep3Login)
  const loginEmail = document.getElementById("popupEmailLogin");
  const loginPassword = document.getElementById("popupPasswordLogin");
  if (loginEmail && loginPassword) {
    [loginEmail, loginPassword].forEach(input => {
      input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          window.loginUser();
        }
      });
    });
  }

  // 3. Enter on Signup Info Step 1 (popupStep3Signup1 → name, phone, pass)
  const nameInput = document.getElementById("popupName");
  const phoneInput = document.getElementById("popupPhone");
  const passInput = document.getElementById("popupPasswordNew");
  const confirmInput = document.getElementById("popupConfirmPassword");

  if (nameInput && phoneInput && passInput && confirmInput) {
    [nameInput, phoneInput, passInput, confirmInput].forEach(input => {
      input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          window.goToJobPreferenceStep();
        }
      });
    });
  }

  // 4. Enter on Signup Final Step (popupStep3Signup2 → category/location checkboxes)
  const categoryBox = document.getElementById("categoryBox");
  const locationBox = document.getElementById("locationBox");
  const signupButton = document.getElementById("signupButton");

  if (categoryBox && locationBox && signupButton) {
    [categoryBox, locationBox].forEach(container => {
      container.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          window.signupUser();
        }
      });
    });

    // Also allow Enter on the button itself (for accessibility)
    signupButton.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        window.signupUser();
      }
    });
  }
});


// Function to update the "All Categories" or "All Locations" checkbox based on individual selections
function updateAllCheckboxStatus(containerId) {
  const container = document.getElementById(containerId);
  const checkboxes = container.querySelectorAll('input[type="checkbox"]');
  const allCheckbox = checkboxes[0]; // The first checkbox is the "All" checkbox

  // Count how many checkboxes are checked (excluding the "All" checkbox)
  const checkedCount = Array.from(checkboxes).slice(1).filter(checkbox => checkbox.checked).length;

  // If all checkboxes (except "All") are checked, check the "All" checkbox
  allCheckbox.checked = (checkedCount === checkboxes.length - 1);
}




// Function to handle "All Categories" or "All Locations" checkbox click
function handleAllCheckboxClick(containerId) {
  const container = document.getElementById(containerId);
  const checkboxes = container.querySelectorAll('input[type="checkbox"]');
  const allCheckbox = checkboxes[0]; // The first checkbox is the "All" checkbox

  checkboxes.forEach((checkbox, index) => {
    // Apply same state to all (except the "All" checkbox is already handled)
    if (index > 0) {
      checkbox.checked = allCheckbox.checked;
    }
  });
}

// Add event listeners to handle changes on category checkboxes
document.getElementById("categoryBox").addEventListener("change", function (e) {
  if (e.target.value === "all-categories") { // If the "All Categories" checkbox is clicked
    handleAllCheckboxClick("categoryBox");
  } else {
    updateAllCheckboxStatus("categoryBox");
  }
});

// Add event listeners to handle changes on job type checkboxes
const jobTypeBoxCheckboxContainer = document.getElementById("jobTypeBox");
if (jobTypeBoxCheckboxContainer) {
  jobTypeBoxCheckboxContainer.addEventListener("change", function (e) {
    if (e.target.value === "all-job-types") {
      handleAllCheckboxClick("jobTypeBox");
    } else {
      updateAllCheckboxStatus("jobTypeBox");
    }
  });
}

// Dynamic regions map loaded from JSON
let popupRegions = {};

async function initDynamicRegions() {
  try {
    const resp = await fetch('/data/all_jobs_loc.json');
    if (!resp.ok) return;
    const data = await resp.json();
    for (const [region, cities] of Object.entries(data)) {
      // use lowercased region name as slug, same as popup options
      popupRegions[region.toLowerCase()] = cities.map(c => c.toLowerCase());
    }
  } catch (e) {
    console.error("Error loading dynamic regions:", e);
  }
}
initDynamicRegions();

// Function to handle region selection
function handleRegionSelection(regionId, containerId = "locationBox") {
  const container = document.getElementById(containerId);
  if (!container) return;
  const checkboxes = container.querySelectorAll('input[type="checkbox"]');

  // Find the exact checked state of the region checkbox that was just clicked
  let isChecked = false;
  checkboxes.forEach(cb => {
    if (cb.value === regionId) {
      isChecked = cb.checked;
    }
  });

  // Check/uncheck all locations inside the region based on the parent region checkbox
  if (popupRegions[regionId]) {
    checkboxes.forEach(cb => {
      if (popupRegions[regionId].includes(cb.value)) {
        cb.checked = isChecked;
      }
    });
  }

  // Also update "All Locations" checkbox status
  updateAllCheckboxStatus(containerId);
}

// Unified event listener to handle changes on location checkboxes including regions
document.getElementById("locationBox").addEventListener("change", function (e) {
  if (e.target.value === "all-location") {
    handleAllCheckboxClick("locationBox");
  } else if (popupRegions[e.target.value]) {
    // If a region header is clicked, select/deselect all its sub-cities dynamically
    handleRegionSelection(e.target.value, "locationBox");
  } else {
    // Standard city checkbox toggle
    updateAllCheckboxStatus("locationBox");
  }
});
