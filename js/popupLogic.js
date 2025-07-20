// /js/popupLogic.js

import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import {
  getFirestore, collection, query, where, getDocs,
  doc, setDoc, getDoc, updateDoc, arrayUnion, Timestamp, deleteField, arrayRemove,
} from "https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js";
import {
  getAuth, createUserWithEmailAndPassword,
  signInWithEmailAndPassword, sendPasswordResetEmail
} from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";
import { onAuthStateChanged } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";
import { getMessaging, getToken, onMessage, deleteToken } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-messaging.js";




let ignoreNextOutsideClick = false;
let allowPopupClose = false;


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

let messaging;

async function initMessaging() {
  if ('serviceWorker' in navigator) {
    try {
      const registration = await navigator.serviceWorker.register('/firebase-messaging-sw.js');
      console.log('Service Worker registered:', registration);
      messaging = getMessaging(app);

      // 🔽 Place onMessage HERE, after messaging is initialized
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

    } catch (error) {
      console.error('Service Worker registration failed:', error);
    }
  } else {
    console.warn('Service Workers not supported in this browser.');
  }
}

initMessaging(); // ✅ Make sure this is called on load



async function logFcmToken() {
  if (!messaging) {
    console.warn('Messaging is not initialized yet');
    return;
  }

  try {
    const token = await getOrCreateFcmToken();
    if (token) {
      console.log('FCM token:', token);
    } else {
      console.warn('No FCM token obtained');
    }
  } catch (error) {
    console.error('Error getting FCM token:', error);
  }
}




const LS_TOKEN_KEY = "currentFcmToken";
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
    document.getElementById("jobAlertPopup").style.display = "flex";
  } else {
    // Hide the jobAlertPopup for other steps
    document.getElementById("jobAlertPopup").style.display = "none";
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

  document.getElementById("jobAlertPopup").style.display = "none";
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
  const checkboxes = container?.querySelectorAll('input[type="checkbox"]:checked') || [];
  const allCheckbox = container?.querySelector('input[value=""]');
  const allSelected = allCheckbox && allCheckbox.checked;
  let selected = [];

  if (allSelected) {
    const allValues = container.querySelectorAll('input[type="checkbox"]');
    allValues.forEach(cb => {
      const val = cb.value.trim();
      if (val !== "") selected.push(val);
    });
  } else {
    checkboxes.forEach(cb => {
      const val = cb.value.trim();
      if (val !== "") selected.push(val);
    });
  }
  return selected;
}

window.handlePopupYes = async () => {
  try {
    if ("Notification" in window) {
      const permission = Notification.permission;
      if (permission === "default") {
        const result = await Notification.requestPermission();
        console.log("Notification permission result:", result);
      }
    }
  } catch (e) {
    console.warn("Notification permission check failed:", e);
  }

  showPopupStep("popupStep2");

  document.getElementById("jobAlertPopup").style.display = "none";
  document.getElementById("profile-card-container").style.display = "block";
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

  const q = query(collection(db, "users"), where("email", "==", email));
  const querySnapshot = await getDocs(q);
  emailExists = !querySnapshot.empty;

  if (emailExists) {
    document.getElementById("popupEmailLogin").value = email;
    showPopupStep("popupStep3Login");
  } else {
    showPopupStep("popupStep3Signup1");
  }

  // **Hide the job alert popup immediately after email existence check**
  document.getElementById("jobAlertPopup").style.display = "none";
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
  document.getElementById("jobAlertPopup").style.display = "none";
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
    "signupError",
    "categoryError",
    "locationError"
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

  if (hasError) {
    signupButton.disabled = false;  // Re-enable the button in case of error
    return;
  }

  try {
    // 1. Create the user in Firebase Auth
    const userCredential = await createUserWithEmailAndPassword(auth, email, password);
    const user = userCredential.user;

    const timestampNow = Timestamp.now();

    // 2. Get the FCM token properly
    let fcmToken = "";
    try {
      fcmToken = await getOrCreateFcmToken();
      console.log("Signup FCM token obtained:", fcmToken);
    } catch (e) {
      console.warn("Unable to get FCM token during signup:", e);
    }

    // 3. Store user details in Firestore with all requested fields
    await setDoc(doc(db, "users", user.uid), {
      uid: user.uid,
      email: user.email,
      phoneNumber: phone,
      fullName: name,
      jobCategory: jobCategory,
      jobLocation: jobLocation,
      createdAt: timestampNow,
      lastLogin: timestampNow,
      fcmTokens: [],  // Ensure this array is always created
      profilePictureUrl: ""  // 👈 default blank profile picture
    });


    // 4. Save to localStorage
    localStorage.setItem("user", JSON.stringify({
      uid: user.uid,
      email: user.email
    }));

    if (fcmToken) {
      await updateFcmToken(user.uid);  // Already handles duplicates
    }


    // 6. Finalize - Show signup success popup
    showPopupStep("popupSignupSuccess");

    console.log("Signup completed with FCM token stored for:", user.uid);

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

    // Update lastLogin timestamp after successful login
    await updateDoc(doc(db, "users", user.uid), {
      lastLogin: Timestamp.now()
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

      const token = await getOrCreateFcmToken();
      if (token) {
        const userRef = doc(db, "users", user.uid);
        const userSnap = await getDoc(userRef);
        if (userSnap.exists()) {
          const data = userSnap.data();
          const currentTokens = data.fcmTokens || [];

          // Add only if token doesn't already exist
          if (!currentTokens.includes(token)) {
            await updateDoc(userRef, {
              fcmTokens: arrayUnion(token)
            });

            console.log("Unique FCM token saved:", token);
          } else {
            console.log("FCM token already exists. No update needed.");
          }
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
    const passwordErrorDiv = document.getElementById("popupPasswordLoginError");
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
    const user = auth.currentUser;
    const token = localStorage.getItem("currentFcmToken") || localStorage.getItem(LS_TOKEN_KEY);

    if (user && token && messaging) {
      try {
        // 1. Remove token from Firestore
        const userRef = doc(db, "users", user.uid);
        await updateDoc(userRef, {
          fcmTokens: arrayRemove(token)
        });
        console.log("FCM token removed from Firestore.");

        // 2. Delete token from Firebase Messaging
        const deleted = await deleteToken(messaging);
        if (deleted) {
          console.log("FCM token deleted from Firebase Messaging.");
        } else {
          console.warn("FCM token could not be deleted.");
        }
      } catch (err) {
        console.error("Error removing FCM token during logout:", err);
      }
    }

    // 3. Clear tokens from localStorage
    localStorage.removeItem("currentFcmToken");
    localStorage.removeItem(LS_TOKEN_KEY);

    // 4. Logout user
    await auth.signOut();

    // 5. Clear session data
    localStorage.removeItem("user");
    localStorage.removeItem("jobAlertPopupShown");
    localStorage.removeItem("LS_SKIP_NO_CONFIRM");

    // 6. Reload page
    location.reload();

  } catch (error) {
    console.error("Logout failed:", error);
  }
});




async function fcmSupported() {
  return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

async function getOrCreateFcmToken() {
  if (!(await fcmSupported())) {
    console.warn("Web FCM not supported on this browser/device.");
    return null;
  }

  // Check if token is already cached in localStorage
  const cached = localStorage.getItem(LS_TOKEN_KEY);
  if (cached) return cached;

  // If notification permission is "default" (i.e., not decided yet), ask for permission
  if (Notification.permission === "default") {
    const permission = await Notification.requestPermission();
    if (permission !== "granted") return null;  // Exit if permission is not granted
  }

  // If permission is still not granted, exit early
  if (Notification.permission !== "granted") return null;

  // Register Service Worker for Firebase messaging
  let registration = await navigator.serviceWorker.getRegistration('/');
  if (!registration) {
    await navigator.serviceWorker.register('/firebase-messaging-sw.js', { scope: '/' });
    registration = await navigator.serviceWorker.ready;
  }

  // Get FCM token
  const token = await getToken(messaging, {
    vapidKey: "BMAg3rxpHjJdssyUfVzCcqrP-k89h_OtRzlmQ2OPPQQzoRrKhVeR73JMd6oZ91zO0J_Kx4K2avuIGIbF14RjWIY",
    serviceWorkerRegistration: registration
  });

  // If a token is generated, store it in localStorage and update Firebase
  if (token) {
    localStorage.setItem(LS_TOKEN_KEY, token);

    // Get the user data
    const user = JSON.parse(localStorage.getItem("user"));
    if (user?.uid) {
      const userRef = doc(db, "users", user.uid);
      const docSnap = await getDoc(userRef);

      if (docSnap.exists()) {
        const userData = docSnap.data();
        const existingTokens = userData.fcmTokens || [];

        // Only update if the token is not already stored in Firestore
        if (!existingTokens.includes(token)) {
          await updateDoc(userRef, {
            fcmTokens: arrayUnion(token)
          });
          console.log("FCM token successfully saved to Firestore.");
        } else {
          console.log("FCM token already exists, skipping.");
        }
      }
    }
  }

  return token;
}



async function syncFcmTokenWithFirestore(uid) {
  if (!uid) return;
  try {
    const registration = await navigator.serviceWorker.ready;
    const currentToken = await getToken(messaging, {
      vapidKey: "BMAg3rxpHjJdssyUfVzCcqrP-k89h_OtRzlmQ2OPPQQzoRrKhVeR73JMd6oZ91zO0J_Kx4K2avuIGIbF14RjWIY",
      serviceWorkerRegistration: registration
    });
    if (!currentToken) return;

    const userRef = doc(db, "users", uid);
    const docSnap = await getDoc(userRef);
    if (!docSnap.exists()) return;

    const userData = docSnap.data();
    const existingTokens = userData.fcmTokens || [];

    if (!existingTokens.includes(currentToken)) {
      await updateDoc(userRef, {
        fcmTokens: arrayUnion(currentToken)
      });

      let storedUser = JSON.parse(localStorage.getItem("user"));
      if (storedUser && storedUser.uid === uid) {
        storedUser.fcmTokens = [...existingTokens, currentToken];
        localStorage.setItem("user", JSON.stringify(storedUser));
      }
    }
  } catch (error) {
    console.warn("Error syncing FCM token:", error);
  }
}

window.addEventListener("load", () => {
  const neverShowPopup = localStorage.getItem("neverShowJobAlertPopup") === "true";

  onAuthStateChanged(auth, async (user) => {
    if (user) {
      // User is signed in
      // Initialize messaging and log FCM token for the signed-in user
      try {
        await initMessaging();
        const token = await getOrCreateFcmToken();
        if (token) {
          console.log("FCM token:", token);
        } else {
          console.warn("No FCM token obtained");
        }
      } catch (error) {
        console.error("Error initializing messaging or getting token:", error);
      }

      // DO NOT show popupStep1 if user is logged in
    } else {
      // Only show popupStep1 if not logged in and neverShowPopup is false
      if (!neverShowPopup) {
        showPopupStep("popupStep1");
      } else {
        closePopup();
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


async function updateFcmToken(uid) {
  try {
    const currentToken = await getToken(messaging, {
      vapidKey: "BMAg3rxpHjJdssyUfVzCcqrP-k89h_OtRzlmQ2OPPQQzoRrKhVeR73JMd6oZ91zO0J_Kx4K2avuIGIbF14RjWIY"
    });

    if (!currentToken) {
      console.warn("No FCM token retrieved");
      return;
    }

    const userRef = doc(db, "users", uid);
    const userSnap = await getDoc(userRef);

    if (userSnap.exists()) {
      const userData = userSnap.data();
      const existingTokens = userData.fcmTokens || [];

      // Only add the token if it's not already stored
      if (!existingTokens.includes(currentToken)) {
        await updateDoc(userRef, {
          fcmTokens: arrayUnion(currentToken)
        });
        console.log("New FCM token added.");
      } else {
        console.log("FCM token already exists. Skipping update.");
      }
    }
  } catch (error) {
    console.error("Error updating FCM token:", error);
  }
}






window.addEventListener("DOMContentLoaded", () => {
  const skipNoConfirm = localStorage.getItem("LS_SKIP_NO_CONFIRM");
  const user = JSON.parse(localStorage.getItem("user"));

  if (!("Notification" in window) || !user?.uid) return;

  setTimeout(() => {
    const permission = Notification.permission;

    if ((permission === "denied" || permission === "default") && skipNoConfirm !== "true") {
      const blockedPopup = document.getElementById("popupBlockedNotifications");

      if (blockedPopup) {
        document.getElementById("jobAlertPopup").style.display = "flex";
        blockedPopup.style.display = "flex";
      }
    }
  }, 100); // Delay helps browser finish determining permission
});


document.getElementById("yesButtonBlockedNotifications")?.addEventListener("click", () => {
  localStorage.setItem("LS_SKIP_NO_CONFIRM", "true");
  document.getElementById("popupBlockedNotifications").style.display = "none";
  document.getElementById("jobAlertPopup").style.display = "none";
});


document.getElementById("noButtonBlockedNotifications")?.addEventListener("click", async () => {
  const user = JSON.parse(localStorage.getItem("user"));
  if (!user?.uid) {
    // Don't do anything if not logged in
    console.warn("User not logged in — skipping notification permission request.");
    return;
  }

  const permission = Notification.permission;

  if (permission === "default") {
    try {
      const result = await Notification.requestPermission();
      if (result === "granted") {
        // Hide both the popup and job alert popup
        document.getElementById("popupBlockedNotifications").style.display = "none";
        document.getElementById("jobAlertPopup").style.display = "none";
        
        // Update the FCM token
        await updateFcmToken(user.uid);
      } else {
        // If permission is denied, show the enable notification popup
        document.getElementById("popupBlockedNotifications").style.display = "none";
        document.getElementById("popupEnableNotifications").style.display = "flex";
        document.getElementById("jobAlertPopup").style.display = "flex";
      }
    } catch (e) {
      console.error("Permission request failed:", e);
    }
  } else if (permission === "denied") {
    // If permission is denied, show enable notification popup
    document.getElementById("popupBlockedNotifications").style.display = "none";
    document.getElementById("popupEnableNotifications").style.display = "flex";
    document.getElementById("jobAlertPopup").style.display = "flex";
  } else if (permission === "granted") {
    // If permission is already granted, just hide both the popup and job alert popup
    document.getElementById("popupBlockedNotifications").style.display = "none";
    document.getElementById("jobAlertPopup").style.display = "none";
  }
});



document.querySelector(".blockclosebtn")?.addEventListener("click", () => {
  document.getElementById("popupEnableNotifications").style.display = "none";
  document.getElementById("jobAlertPopup").style.display = "none";
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



document.getElementById("logoffbtn")?.addEventListener("click", async (e) => {
  e.preventDefault(); // just in case
  try {
    await auth.signOut();
    localStorage.removeItem("user");
    localStorage.removeItem("jobAlertPopupShown");
    localStorage.removeItem(LS_SKIP_NO_CONFIRM);
    location.reload();
  } catch (error) {
    console.error("Logout failed:", error);
  }
});
