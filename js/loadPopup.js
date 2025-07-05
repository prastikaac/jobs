
    const jobAlertPopup = document.createElement("div");
    jobAlertPopup.id = "jobAlertPopup";
    jobAlertPopup.className = "popup";
    jobAlertPopup.style.display = "none";

    document.body.appendChild(jobAlertPopup);

    // popupStep1
    const popupStep1 = document.createElement("div");
    popupStep1.className = "popup-content";
    popupStep1.id = "popupStep1";
    popupStep1.innerHTML = `
  <p>Want to get job alerts?</p>
  <p>
    <img src="images/job-alert.jpg" alt="">
    You’ll be notified about new job postings that match your preferences.
    We’ll instantly update you via email and notifications whenever relevant jobs are posted.
  </p>
  <button onclick="handlePopupYes()">Yes</button>
  <button onclick="handlePopupNo()">No</button>
`;
    jobAlertPopup.appendChild(popupStep1);

    // popupStep1b
    const popupStep1b = document.createElement("div");
    popupStep1b.className = "popup-content";
    popupStep1b.id = "popupStep1b";
    popupStep1b.style.display = "none";
    popupStep1b.innerHTML = `
  <p>
    Are you sure you don’t want job alerts? Since you pressed ‘No’, you won’t be notified about new jobs matching
    your interests.<br><br>
    Otherwise, we instantly update you via email and notifications whenever relevant jobs are posted.<br><br>
    Stay ahead — enable alerts to never miss an opportunity.
  </p>
  <button onclick="handleNoSkipAlerts()">No, skip alerts</button>
  <button onclick="handlePopupYes()">Yes, notify me</button>
`;
    jobAlertPopup.appendChild(popupStep1b);

    // popupStep1c
    const popupStep1c = document.createElement("div");
    popupStep1c.className = "popup-content";
    popupStep1c.id = "popupStep1c";
    popupStep1c.style.display = "none";
    popupStep1c.innerHTML = `
  <p>Are you absolutely sure you want to skip job alerts?</p>
  <label style="display:flex;align-items:center;justify-content:center;margin-top:10px;">
    <input type="checkbox" id="neverShowAgain" style="margin-right:10px;"> Never show this message again
  </label>
  <button onclick="confirmFinalNo(true)">Yes, I’m sure</button>
  <button onclick="handlePopupYes()">No, go back</button>
`;
    jobAlertPopup.appendChild(popupStep1c);

    // popupStep2
    const popupStep2 = document.createElement("div");
    popupStep2.className = "popup-content";
    popupStep2.id = "popupStep2";
    popupStep2.style.display = "none";
    popupStep2.innerHTML = `
  <div style="position: relative;">
    <input type="email" id="popupEmail" placeholder="Enter your email" required />
    <span style="position: absolute; left: 10px; top: 50%; transform: translateY(-50%);">
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-envelope"
        viewBox="0 0 16 16">
        <path
          d="M0 4a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2zm2-1a1 1 0 0 0-1 1v.217l7 4.2 7-4.2V4a1 1 0 0 0-1-1zm13 2.383-4.708 2.825L15 11.105zm-.034 6.876-5.64-3.471L8 9.583l-1.326-.795-5.64 3.47A1 1 0 0 0 2 13h12a1 1 0 0 0 .966-.741M1 11.105l4.708-2.897L1 5.383z" />
      </svg>
    </span>
    <div id="popupEmailError" class="error-message"></div>
  </div>
  <button onclick="checkEmailExistence()">Continue</button>
`;
    jobAlertPopup.appendChild(popupStep2);

    // popupStep3Signup1
    const popupStep3Signup1 = document.createElement("div");
    popupStep3Signup1.className = "popup-content";
    popupStep3Signup1.id = "popupStep3Signup1";
    popupStep3Signup1.style.display = "none";
    popupStep3Signup1.innerHTML = `
  <div style="position: relative;">
    <input type="text" id="popupName" placeholder="Full Name" required />
    <span style="position: absolute; left: 10px; top: 50%; transform: translateY(-50%);">
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-person"
        viewBox="0 0 16 16">
        <path
          d="M8 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6m2-3a2 2 0 1 1-4 0 2 2 0 0 1 4 0m4 8c0 1-1 1-1 1H3s-1 0-1-1 1-4 6-4 6 3 6 4m-1-.004c-.001-.246-.154-.986-.832-1.664C11.516 10.68 10.289 10 8 10s-3.516.68-4.168 1.332c-.678.678-.83 1.418-.832 1.664z" />
      </svg>
    </span>
    <div id="popupNameError" class="error-message"></div>
  </div>

  <div style="position: relative;">
    <input type="tel" id="popupPhone" placeholder="Phone Number" required />
    <span style="position: absolute; left: 10px; top: 50%; transform: translateY(-50%);">
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-telephone"
        viewBox="0 0 16 16">
        <path
          d="M3.654 1.328a.678.678 0 0 0-1.015-.063L1.605 2.3c-.483.484-.661 1.169-.45 1.77a17.6 17.6 0 0 0 4.168 6.608 17.6 17.6 0 0 0 6.608 4.168c.601.211 1.286.033 1.77-.45l1.034-1.034a.678.678 0 0 0-.063-1.015l-2.307-1.794a.68.68 0 0 0-.58-.122l-2.19.547a1.75 1.75 0 0 1-1.657-.459L5.482 8.062a1.75 1.75 0 0 1-.46-1.657l.548-2.19a.68.68 0 0 0-.122-.58z" />
      </svg>
    </span>
    <div id="popupPhoneError" class="error-message"></div>
  </div>

  <div style="position: relative;">
    <input type="password" id="popupPasswordNew" placeholder="Create Password" required />
    <span style="position: absolute; left: 10px; top: 50%; transform: translateY(-50%);">
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-lock"
        viewBox="0 0 16 16">
        <path fill-rule="evenodd"
          d="M8 0a4 4 0 0 1 4 4v2.05a2.5 2.5 0 0 1 2 2.45v5a2.5 2.5 0 0 1-2.5 2.5h-7A2.5 2.5 0 0 1 2 13.5v-5a2.5 2.5 0 0 1 2-2.45V4a4 4 0 0 1 4-4M4.5 7A1.5 1.5 0 0 0 3 8.5v5A1.5 1.5 0 0 0 4.5 15h7a1.5 1.5 0 0 0 1.5-1.5v-5A1.5 1.5 0 0 0 11.5 7zM8 1a3 3 0 0 0-3 3v2h6V4a3 3 0 0 0-3-3" />
      </svg>
    </span>
    <span class="toggle-password" onclick="togglePassword(this)">Show</span>
    <div id="popupPasswordError" class="error-message"></div>
  </div>

  <div style="position: relative;">
    <input type="password" id="popupConfirmPassword" placeholder="Confirm Password" required />
    <span style="position: absolute; left: 10px; top: 50%; transform: translateY(-50%);">
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-lock"
        viewBox="0 0 16 16">
        <path fill-rule="evenodd"
          d="M8 0a4 4 0 0 1 4 4v2.05a2.5 2.5 0 0 1 2 2.45v5a2.5 2.5 0 0 1-2.5 2.5h-7A2.5 2.5 0 0 1 2 13.5v-5a2.5 2.5 0 0 1 2-2.45V4a4 4 0 0 1 4-4M4.5 7A1.5 1.5 0 0 0 3 8.5v5A1.5 1.5 0 0 0 4.5 15h7a1.5 1.5 0 0 0 1.5-1.5v-5A1.5 1.5 0 0 0 11.5 7zM8 1a3 3 0 0 0-3 3v2h6V4a3 3 0 0 0-3-3" />
      </svg>
    </span>
    <span class="toggle-password" onclick="togglePassword(this)">Show</span>
    <div id="popupConfirmPasswordError" class="error-message"></div>
  </div>
  <div id="signupError" style="color:red; margin-top: 8px;"></div>
  <button onclick="goToJobPreferenceStep()">Continue</button>
`;
    jobAlertPopup.appendChild(popupStep3Signup1);

    // popupStep3Signup2
    const popupStep3Signup2 = document.createElement("div");
    popupStep3Signup2.className = "popup-content";
    popupStep3Signup2.id = "popupStep3Signup2";
    popupStep3Signup2.style.display = "none";
    popupStep3Signup2.innerHTML = `
  <h3>What kind of jobs are you interested in?</h3>
  <div class="select-box" id="categoryBox">
    <div class="option-row">
      <span>All Categories</span>
      <label class="switch">
        <input type="checkbox" value="">
        <span class="slider"></span>
      </label>
    </div>
    <div class="option-row">
      <span>IT & Tech</span>
      <label class="switch">
        <input type="checkbox" value="it-tech">
        <span class="slider"></span>
      </label>
    </div>
  </div>
  <div id="categoryError" class="error-message"></div>

  <h3>Where do you want to work?</h3>
  <div class="select-box" id="locationBox">
    <div class="option-row">
      <span>All Locations</span>
      <label class="switch">
        <input type="checkbox" value="">
        <span class="slider"></span>
      </label>
    </div>
    <div class="option-row">
      <span>Helsinki</span>
      <label class="switch">
        <input type="checkbox" value="helsinki">
        <span class="slider"></span>
      </label>
    </div>
  </div>
  <div id="locationError" class="error-message"></div>
  <div id="signupPrefError" style="color:red; margin-top:8px;"></div>
  <button onclick="signupUser()">Sign Up</button>
`;
    jobAlertPopup.appendChild(popupStep3Signup2);

    // popupStep3Login
    const popupStep3Login = document.createElement("div");
    popupStep3Login.className = "popup-content";
    popupStep3Login.id = "popupStep3Login";
    popupStep3Login.style.display = "none";
    popupStep3Login.innerHTML = `
  <input type="email" id="popupEmailLogin" readonly />
  <div style="position: relative;">
    <input type="password" id="popupPasswordLogin" placeholder="Enter Password" required />
    <span style="position: absolute; left: 10px; top: 50%; transform: translateY(-50%);">
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-lock"
        viewBox="0 0 16 16">
        <path fill-rule="evenodd"
          d="M8 0a4 4 0 0 1 4 4v2.05a2.5 2.5 0 0 1 2 2.45v5a2.5 2.5 0 0 1-2.5 2.5h-7A2.5 2.5 0 0 1 2 13.5v-5a2.5 2.5 0 0 1 2-2.45V4a4 4 0 0 1 4-4M4.5 7A1.5 1.5 0 0 0 3 8.5v5A1.5 1.5 0 0 0 4.5 15h7a1.5 1.5 0 0 0 1.5-1.5v-5A1.5 1.5 0 0 0 11.5 7zM8 1a3 3 0 0 0-3 3v2h6V4a3 3 0 0 0-3-3" />
      </svg>
    </span>
    <span class="toggle-password" onclick="togglePassword(this)">Show</span>
    <div id="popupPasswordLoginError" class="error-message"></div>
  </div>
  <button onclick="loginUser()">Login</button>
`;
    jobAlertPopup.appendChild(popupStep3Login);

    // logout button
    const logoutBtn = document.createElement("button");
    logoutBtn.id = "logoutBtn";
    logoutBtn.style.position = "fixed";
    logoutBtn.style.top = "10px";
    logoutBtn.style.right = "10px";
    logoutBtn.textContent = "Logout";
    logoutBtn.addEventListener("click", function () {
      // you can add logout logic here
    });
    document.body.appendChild(logoutBtn);

  