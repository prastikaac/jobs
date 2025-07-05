
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import {
  getFirestore, collection, query, where, getDocs,
  doc, setDoc, getDoc, updateDoc, arrayUnion, Timestamp
} from "https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js";
import { getMessaging, getToken } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-messaging.js";
import {
  getAuth, createUserWithEmailAndPassword,
  signInWithEmailAndPassword, sendPasswordResetEmail
} from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";


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
const messaging = getMessaging(app);

const LS_TOKEN_KEY = "currentFcmToken";
const LS_SKIP_NO_CONFIRM = "skipNoConfirm";

let emailExists = false;

function showPopupStep(stepId) {
  const steps = [
    "popupStep1",
    "popupStep1b",
    "popupStep1c",
    "popupStep2",
    "popupStep3Signup1",
    "popupStep3Signup2",
    "popupStep3Login"
  ];

  steps.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.display = (id === stepId) ? "block" : "none";
  });

  // Show the jobAlertPopup only for steps "popupStep1", "popupStep1b", "popupStep1c"
  if (["popupStep1", "popupStep1b", "popupStep1c"].includes(stepId)) {
    document.getElementById("jobAlertPopup").style.display = "flex";
  } else {
    // Hide jobAlertPopup for other steps
    document.getElementById("jobAlertPopup").style.display = "none";
  }
}


function closePopup() {
  localStorage.setItem("jobAlertPopupShown", "true");
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

window.handlePopupYes = () => {
  // Show the next step in the popup (either go to login/signup)
  showPopupStep("popupStep2");

  // Hide the job alert popup and show the profile card container
  document.getElementById("jobAlertPopup").style.display = "none";
  document.getElementById("profile-card-container").style.display = "block";
};


window.handlePopupNo = () => {
  const skipNoConfirm = localStorage.getItem(LS_SKIP_NO_CONFIRM);
  if (skipNoConfirm === "true") {
    closePopup();
    return;
  }
  // Show the confirmation step to skip alerts
  showPopupStep("popupStep1b");
};

window.handleNoSkipAlerts = () => {
  showPopupStep("popupStep1c");
};

window.confirmFinalNo = () => {
  const neverShowCheckbox = document.getElementById("neverShowAgain");
  if (neverShowCheckbox && neverShowCheckbox.checked) {
    localStorage.setItem(LS_SKIP_NO_CONFIRM, "true");
  }
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

  // Continue to preferences step
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

  if (hasError) return;

  try {
    // Further processing...
  } catch (error) {
    console.error("Signup error:", error);
  }
};

window.loginUser = async () => {
  clearAllErrors();

  const emailInput = document.getElementById("popupEmailLogin");
  const passInput = document.getElementById("popupPasswordLogin");
  const email = emailInput.value.trim();
  const password = passInput.value;

  if (!validatePassword(password)) {
    showFieldError(passInput, "Please enter a valid password (min 6 chars).");
    passInput.focus();
    return;
  }

  try {
    const userCredential = await signInWithEmailAndPassword(auth, email, password);
    const user = userCredential.user;

    // Save user in localStorage if needed
    localStorage.setItem("user", JSON.stringify({
      uid: user.uid,
      email: user.email
    }));

    await syncFcmTokenWithFirestore(user.uid);

    // Hide popup and show the profile
    document.getElementById("jobAlertPopup").style.display = "none";
    document.getElementById("profile-card-container").style.display = "block";

  } catch (error) {
    console.error("Login failed:", error);
    if (error.code === "auth/wrong-password") {
      showFieldError(passInput, "The password you entered is incorrect. Please try again.");
      passInput.focus();
    } else if (error.code === "auth/user-not-found") {
      showFieldError(emailInput, "No account found with this email.");
      emailInput.focus();
    } else {
      showFieldError(passInput, "Login failed. Please check your credentials and try again.");
    }
  }
};



document.getElementById("logoutBtn")?.addEventListener("click", async () => {
  try {
    await auth.signOut();
    localStorage.removeItem("user");
    localStorage.removeItem("jobAlertPopupShown");
    localStorage.removeItem(LS_SKIP_NO_CONFIRM);
    // You can show a message on the page instead of alert if needed
    location.reload();
  } catch (error) {
    console.error("Logout failed:", error);
    // Optional: show logout failure inline message
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
  const cached = localStorage.getItem(LS_TOKEN_KEY);
  if (cached) return cached;

  if (Notification.permission === "default") {
    const permission = await Notification.requestPermission();
    if (permission !== "granted") return null;
  }

  if (Notification.permission !== "granted") return null;

  let registration = await navigator.serviceWorker.getRegistration('/');
  if (!registration) {
    await navigator.serviceWorker.register('/firebase-messaging-sw.js', { scope: '/' });
    registration = await navigator.serviceWorker.ready;
  }

  const token = await getToken(messaging, {
    vapidKey: "BMAg3rxpHjJdssyUfVzCcqrP-k89h_OtRzlmQ2OPPQQzoRrKhVeR73JMd6oZ91zO0J_Kx4K2avuIGIbF14RjWIY",
    serviceWorkerRegistration: registration
  });

  if (token) localStorage.setItem(LS_TOKEN_KEY, token);
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

window.addEventListener("load", async () => {
  const user = JSON.parse(localStorage.getItem("user"));
  const skipNoConfirm = localStorage.getItem(LS_SKIP_NO_CONFIRM);

  if (user && user.uid) {
    await syncFcmTokenWithFirestore(user.uid);
  }

  if (!user && skipNoConfirm !== "true") {
    showPopupStep("popupStep1");
  } else {
    closePopup();
  }
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
