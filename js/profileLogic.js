// Firebase imports
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import { getAuth, onAuthStateChanged, signOut } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";
import {
  getFirestore,
  doc,
  getDoc,
  updateDoc
} from "https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js";
import {
  getStorage,
  ref,
  uploadBytes,
  getDownloadURL
} from "https://www.gstatic.com/firebasejs/10.12.2/firebase-storage.js";

// Firebase config
const firebaseConfig = {
  apiKey: "AIzaSyAstAXkwifJ-ukfZKSXiLG_l9iNwg4tPw4",
  authDomain: "findjobsinfinland-3c061.firebaseapp.com",
  projectId: "findjobsinfinland-3c061",
  storageBucket: "findjobsinfinland-3c061.appspot.com",
  messagingSenderId: "575437446165",
  appId: "1:575437446165:web:51922bc01fd291b09b821c"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getFirestore(app);
const storage = getStorage(app, "gs://findjobsinfinland-3c061.firebasestorage.app");

// DOM logic after everything is loaded
document.addEventListener("DOMContentLoaded", () => {
  const cameraIcon = document.getElementById("cameraIcon");
  const imageUploadInput = document.getElementById("imageUploadInput");
  const profileImage = document.getElementById("profileImage");
  const ppCard = document.getElementById("pp-card");
  const editButton = document.getElementById("edit-pp-information");
  const signOutButton = document.getElementById("signout-btn");
  const dissignElements = document.querySelectorAll(".dissign");

  let currentUID = null;

  // Sign-out logic
  signOutButton.addEventListener("click", () => {
    signOut(auth).then(() => {
      // Hide profile and related elements on sign-out
      ppCard.style.display = "none";
      editButton.style.display = "none";
      signOutButton.style.display = "none";
      dissignElements.forEach(el => el.style.display = "none");
    }).catch((error) => {
      console.error("Sign-out error:", error);
    });
  });

  // Check user authentication state
  onAuthStateChanged(auth, async (user) => {
    if (!user) {
      // User not logged in — hide profile and related elements
      ppCard.style.display = "none";
      editButton.style.display = "none";
      signOutButton.style.display = "none";
      dissignElements.forEach(el => el.style.display = "none");
      return;
    }

    // User logged in — show profile and related elements
    ppCard.style.display = "flex";
    editButton.style.display = "block";
    signOutButton.style.display = "block";
    dissignElements.forEach(el => el.style.display = "block");

    currentUID = user.uid;

    // Fetch user data from Firestore
    const userRef = doc(db, "users", currentUID);
    const snap = await getDoc(userRef);

    if (snap.exists()) {
      const data = snap.data();
      profileImage.src = data.profilePictureUrl?.trim() || "/images/user.png";
      document.getElementById("nameText").textContent = data.fullName || "No Name";
      document.getElementById("emailText").textContent = data.email || "No Email";
      document.getElementById("phoneText").textContent = data.phoneNumber || "No Phone";
    }
  });

  // Click on camera icon triggers hidden file input
  cameraIcon.addEventListener("click", () => {
    imageUploadInput.click();
  });

  // Upload image logic
  imageUploadInput.addEventListener("change", async (event) => {
    const file = event.target.files[0];
    if (!file || !currentUID) return;

    // Local preview
    const localUrl = URL.createObjectURL(file);
    profileImage.src = localUrl;

    // Set file path including the filename "image.png"
    const filePath = `profilePictures/${currentUID}/image.png`;
    const storageRef = ref(storage, filePath);

    try {
      // Upload the file to Firebase Storage
      await uploadBytes(storageRef, file);

      // Get the download URL for the uploaded file
      const downloadURL = await getDownloadURL(storageRef);

      // Update Firestore with the new image URL
      await updateDoc(doc(db, "users", currentUID), {
        profilePictureUrl: downloadURL
      });

      // Free memory
      URL.revokeObjectURL(localUrl);
    } catch (err) {
      console.error("Upload or Firestore update failed:", err);
    }
  });

});

document.addEventListener("DOMContentLoaded", () => {
  const popupWrapper = document.getElementById("pp-card-wrapper");
  const closeBtn = document.getElementById("pp-card-closebtn");
  const pcUserDetails = document.getElementById("pcuserdetails");
  const header = document.getElementById("header");

  function setZIndexZero() {
    const header = document.getElementById("header");
    if (header) header.style.zIndex = "1";

    const iFxdElementsNow = document.querySelectorAll(".iFxd");
    iFxdElementsNow.forEach(el => el.style.zIndex = "0");

    const hiddenZIndexElements = document.querySelectorAll(".hidden-z-index, #hidden-z-index");
    hiddenZIndexElements.forEach(el => el.style.zIndex = "0");
  }

  function resetZIndex() {
    const header = document.getElementById("header");
    if (header) header.style.zIndex = "";

    const iFxdElementsNow = document.querySelectorAll(".iFxd");
    iFxdElementsNow.forEach(el => el.style.zIndex = "");

    const hiddenZIndexElements = document.querySelectorAll(".hidden-z-index, #hidden-z-index");
    hiddenZIndexElements.forEach(el => el.style.zIndex = "");
  }

  pcUserDetails.addEventListener("click", (e) => {
    e.preventDefault();
    popupWrapper.classList.add("show");
    setZIndexZero();
  });

  function closetheuserdetailsPopup() {
    popupWrapper.classList.remove("show");
    resetZIndex();
  }

  closeBtn.addEventListener("click", closetheuserdetailsPopup);

  popupWrapper.addEventListener("click", (event) => {
    if (event.target === popupWrapper) {
      closetheuserdetailsPopup();
    }
  });
});
