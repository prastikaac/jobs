
const container = document.getElementById("login-signup-popup-content");

const wrapper = document.createElement("div");
wrapper.id = "profile-card-container";

wrapper.innerHTML = `
    <div class="popup-content" id="popupStep2" style="display:none">
      <h3 class="popup-heading">Get Started</h3>
      <p class="popup-description">Enter your email address to get the latest job openings that matches your job preferences.</p>
      <div class="input-wrapper">
        <input type="email" id="popupEmail" placeholder="Enter your email" required />
        <span class="icon-wrapper">
            <svg xmlns="http://www.w3.org/2000/svg"
                                    viewBox="0 0 512 512"><!--!Font Awesome Free 6.7.2 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc.-->
                                    <path
                                      d="M64 112c-8.8 0-16 7.2-16 16l0 22.1L220.5 291.7c20.7 17 50.4 17 71.1 0L464 150.1l0-22.1c0-8.8-7.2-16-16-16L64 112zM48 212.2L48 384c0 8.8 7.2 16 16 16l384 0c8.8 0 16-7.2 16-16l0-171.8L322 328.8c-38.4 31.5-93.7 31.5-132 0L48 212.2zM0 128C0 92.7 28.7 64 64 64l384 0c35.3 0 64 28.7 64 64l0 256c0 35.3-28.7 64-64 64L64 448c-35.3 0-64-28.7-64-64L0 128z" />
                                  </svg>
        </span>
      </div>
      <div id="popupEmailError" class="error-message"></div>
      <button class="continue-btn" onclick="checkEmailExistence()">Next</button>
    </div>

    <div class="popup-content" id="popupStep3Signup1" style="display:none">
      <h3 class="popup-heading">Create Your Profile</h3>
      <p class="popup-description">Tell us a bit more about yourself to set up your profile and personalize your experience.</p>

      <div class="input-group">
        <label for="popupName">Full Name</label>
        <div class="input-wrapper">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor"
                                    class="bi bi-person" viewBox="0 0 16 16">
                                    <path
                                      d="M8 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6m2-3a2 2 0 1 1-4 0 2 2 0 0 1 4 0m4 8c0 1-1 1-1 1H3s-1 0-1-1 1-4 6-4 6 3 6 4m-1-.004c-.001-.246-.154-.986-.832-1.664C11.516 10.68 10.289 10 8 10s-3.516.68-4.168 1.332c-.678.678-.83 1.418-.832 1.664z" />
                                  </svg>
          <input type="text" id="popupName" placeholder="Enter your full name" required />
        </div>
        <div id="popupNameError" class="error-message"></div>
      </div>

      <div class="input-group">
        <label for="popupPhone">Phone Number</label>
        <div class="input-wrapper">
         <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor"
                                    class="bi bi-telephone" viewBox="0 0 16 16">
                                    <path
                                      d="M3.654 1.328a.678.678 0 0 0-1.015-.063L1.605 2.3c-.483.484-.661 1.169-.45 1.77a17.6 17.6 0 0 0 4.168 6.608 17.6 17.6 0 0 0 6.608 4.168c.601.211 1.286.033 1.77-.45l1.034-1.034a.678.678 0 0 0-.063-1.015l-2.307-1.794a.68.68 0 0 0-.58-.122l-2.19.547a1.75 1.75 0 0 1-1.657-.459L5.482 8.062a1.75 1.75 0 0 1-.46-1.657l.548-2.19a.68.68 0 0 0-.122-.58z" />
                                  </svg>
          <input type="tel" id="popupPhone" placeholder="Enter your phone number" required />
        </div>
        <div id="popupPhoneError" class="error-message"></div>
      </div>

      <div class="input-group">
        <label for="popupPasswordNew">Password</label>
        <div class="input-wrapper">
           <svg style="width: 20px; height: 20px;" xmlns="http://www.w3.org/2000/svg"
                                    fill="currentColor" class="bi bi-lock" viewBox="0 0 16 16">
                                    <path fill-rule="evenodd"
                                      d="M8 0a4 4 0 0 1 4 4v2.05a2.5 2.5 0 0 1 2 2.45v5a2.5 2.5 0 0 1-2.5 2.5h-7A2.5 2.5 0 0 1 2 13.5v-5a2.5 2.5 0 0 1 2-2.45V4a4 4 0 0 1 4-4M4.5 7A1.5 1.5 0 0 0 3 8.5v5A1.5 1.5 0 0 0 4.5 15h7a1.5 1.5 0 0 0 1.5-1.5v-5A1.5 1.5 0 0 0 11.5 7zM8 1a3 3 0 0 0-3 3v2h6V4a3 3 0 0 0-3-3" />
                                  </svg>
          <input type="password" id="popupPasswordNew" placeholder="Create a strong password" required />
          <span class="toggle-password" onclick="togglePassword(this)">Show</span>
        </div>
        <div id="popupPasswordError" class="error-message"></div>
      </div>

      <div class="input-group">
        <label for="popupConfirmPassword">Confirm Password</label>
        <div class="input-wrapper">
          <svg style="width: 20px; height: 20px;" xmlns="http://www.w3.org/2000/svg"
                                    fill="currentColor" class="bi bi-lock" viewBox="0 0 16 16">
                                    <path fill-rule="evenodd"
                                      d="M8 0a4 4 0 0 1 4 4v2.05a2.5 2.5 0 0 1 2 2.45v5a2.5 2.5 0 0 1-2.5 2.5h-7A2.5 2.5 0 0 1 2 13.5v-5a2.5 2.5 0 0 1 2-2.45V4a4 4 0 0 1 4-4M4.5 7A1.5 1.5 0 0 0 3 8.5v5A1.5 1.5 0 0 0 4.5 15h7a1.5 1.5 0 0 0 1.5-1.5v-5A1.5 1.5 0 0 0 11.5 7zM8 1a3 3 0 0 0-3 3v2h6V4a3 3 0 0 0-3-3" />
                                  </svg>
          <input type="password" id="popupConfirmPassword" placeholder="Confirm your password" required />
          <span class="toggle-password" onclick="togglePassword(this)">Show</span>
        </div>
        <div id="popupConfirmPasswordError" class="error-message"></div>
      </div>

      <div id="signupError" style="color:red; margin-top:8px;"></div>
      <button onclick="goToJobPreferenceStep()">Continue</button>
    </div>

    <div class="popup-content" id="popupStep3Signup2" style="display:none">
      <h3 class="popup-heading lasthead">Select your Job Preferences</h3>
      <p class="popup-description" style="margin-top:-2px; margin-bottom:25px;">
        Choose your job preferences, including job roles, locations, working hours, languages, and job types. </p>
      <h3>I. What kind of jobs are you interested in?</h3>
      <p class="popup-description" style="margin-top:-10px; margin-bottom:15px; font-size:14px;">Choose the job industries that interest you the most.</p>
      <div class="select-box" id="categoryBox">
<!-- Dynamically loaded -->
        </div>
        <div id="categoryError" class="error-message"></div>

      <h3>II. Where do you want to work?</h3>
      <p class="popup-description" style="margin-top:-10px; margin-bottom:15px; font-size:14px;">Select the locations where you want to work.</p>
      <div class="select-box" id="locationBox">
<!-- Dynamically loaded -->
        </div>
        <div id="locationError" class="error-message"></div>

      <h3>III. Which job times do you prefer?</h3>
      <p class="popup-description" style="margin-top:-10px; margin-bottom:15px; font-size:14px;">Pick the working hours that suit your schedule.</p>
      <div class="select-box" id="jobTimesBox">
        <div class="option-row"><span>Full-time</span><label class="switch"><input type="checkbox" value="full-time" /><span class="slider"></span></label></div>
        <div class="option-row"><span>Part-time</span><label class="switch"><input type="checkbox" value="part-time" /><span class="slider"></span></label></div>
      </div>
        <div id="jobTimesError" class="error-message"></div>

      <h3>IV. Which languages do you want to work in?</h3>
      <p class="popup-description" style="margin-top:-10px; margin-bottom:15px; font-size:14px;">Select the languages you’re comfortable using at work.</p>
      <div class="select-box" id="jobLangsBox">
        <div class="option-row"><span>Finnish</span><label class="switch"><input type="checkbox" value="finnish" /><span class="slider"></span></label></div>
        <div class="option-row"><span>English</span><label class="switch"><input type="checkbox" value="english" /><span class="slider"></span></label></div>
        <div class="option-row"><span>Swedish</span><label class="switch"><input type="checkbox" value="swedish" /><span class="slider"></span></label></div>
      </div>
        <div id="jobLangsError" class="error-message"></div>

      <h3>V. Which type of job are you looking for?</h3>
      <p class="popup-description" style="margin-top:-10px; margin-bottom:15px; font-size:14px;">Choose the type of employment you are looking for.</p>
      <div class="select-box" id="jobTypeBox">
        <div class="option-row"><span>All types of Job</span><label class="switch"><input type="checkbox" value="all-job-types" /><span class="slider"></span></label></div>
        <div class="option-row"><span>Permanent</span><label class="switch"><input type="checkbox" value="permanent" /><span class="slider"></span></label></div>
        <div class="option-row"><span>Temporary</span><label class="switch"><input type="checkbox" value="temporary" /><span class="slider"></span></label></div>
        <div class="option-row"><span>Seasonal work</span><label class="switch"><input type="checkbox" value="seasonal" /><span class="slider"></span></label></div>
        <div class="option-row"><span>Summer job</span><label class="switch"><input type="checkbox" value="summer" /><span class="slider"></span></label></div>
      </div>
        <div id="jobTypeError" class="error-message"></div>

      <h3>VI. How do you want to receive job alerts?</h3>
      <p class="popup-description" style="margin-top:-10px; margin-bottom:15px; font-size:14px;">Select how you want to receive job updates.</p>
      <div class="select-box" id="jobAlertSubBox">
        <div class="option-row"><span>Email</span><label class="switch"><input type="checkbox" value="email" checked /><span class="slider"></span></label></div>
        <div class="option-row"><span>Push Notification</span><label class="switch"><input type="checkbox" value="pushNotification" checked /><span class="slider"></span></label></div>
      </div>
        <div id="jobAlertSubError" class="error-message"></div>

      <h3>VII. How often do you want to receive job alerts?</h3>
      <p class="popup-description" style="margin-top:-10px; margin-bottom:15px; font-size:14px;">Choose how often you want to get job alerts.</p>
      <div class="select-box" id="jobAlertFreqBox">
        <div class="option-row"><span>Instantly when matching job published</span><label class="switch"><input type="radio" name="jobFreq" value="instantly" checked /><span class="slider"></span></label></div>
        <div class="option-row"><span>Once a day</span><label class="switch"><input type="radio" name="jobFreq" value="daily" /><span class="slider"></span></label></div>
        <div class="option-row"><span>Once a week</span><label class="switch"><input type="radio" name="jobFreq" value="weekly" /><span class="slider"></span></label></div>
        <div class="option-row"><span>Once a month</span><label class="switch"><input type="radio" name="jobFreq" value="monthly" /><span class="slider"></span></label></div>
      </div>
        <div id="jobAlertFreqError" class="error-message"></div>
        <div id="signupPrefError" style="color:red; margin-top:8px;"></div>
        <button id="signupButton" onclick="signupUser()">Sign Up</button>
    </div>

    <div class="popup-content" id="popupStep3Login" style="display:none">
      <h3 class="popup-heading">Welcome Back</h3>
      <p class="popup-description">We've found an account linked to this email. Please enter your password to continue.</p>

      <div class="input-group">
        <div class="input-wrapper">
             <svg xmlns="http://www.w3.org/2000/svg"
                                    viewBox="0 0 512 512"><!--!Font Awesome Free 6.7.2 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc.-->
                                    <path
                                      d="M64 112c-8.8 0-16 7.2-16 16l0 22.1L220.5 291.7c20.7 17 50.4 17 71.1 0L464 150.1l0-22.1c0-8.8-7.2-16-16-16L64 112zM48 212.2L48 384c0 8.8 7.2 16 16 16l384 0c8.8 0 16-7.2 16-16l0-171.8L322 328.8c-38.4 31.5-93.7 31.5-132 0L48 212.2zM0 128C0 92.7 28.7 64 64 64l384 0c35.3 0 64 28.7 64 64l0 256c0 35.3-28.7 64-64 64L64 448c-35.3 0-64-28.7-64-64L0 128z" />
                                  </svg>
          <input type="email" id="popupEmailLogin" placeholder="Enter your email" required />
        </div>
        <div id="popupEmailLoginError" class="error-message"></div>
      </div>

      <div class="input-group">
        <div class="input-wrapper">
           <svg style="width: 20px; height: 20px;" xmlns="http://www.w3.org/2000/svg"
                                    fill="currentColor" class="bi bi-lock" viewBox="0 0 16 16">
                                    <path fill-rule="evenodd"
                                      d="M8 0a4 4 0 0 1 4 4v2.05a2.5 2.5 0 0 1 2 2.45v5a2.5 2.5 0 0 1-2.5 2.5h-7A2.5 2.5 0 0 1 2 13.5v-5a2.5 2.5 0 0 1 2-2.45V4a4 4 0 0 1 4-4M4.5 7A1.5 1.5 0 0 0 3 8.5v5A1.5 1.5 0 0 0 4.5 15h7a1.5 1.5 0 0 0 1.5-1.5v-5A1.5 1.5 0 0 0 11.5 7zM8 1a3 3 0 0 0-3 3v2h6V4a3 3 0 0 0-3-3" />
                                  </svg>
          <input type="password" id="popupPasswordLogin" placeholder="Enter your password" required />
          <span class="toggle-password" onclick="togglePassword(this)">Show</span>
        </div>
        <div id="popupPasswordLoginError" class="error-message"></div>
        <span id="forgotPasswordLink">Forgot Password?</span>
        <div id="forgotPasswordMessage" class="info-message"></div>
      </div>

      <button onclick="loginUser()">Login</button>
    </div>

    <div class="popup-content" id="popupSignupSuccess" style="display:none;">
      <img class="popup-image-pc-and-mobile" src="https://findjobsinfinland.fi/images/sucessfully.png" alt="Signed Up Success">
      <h3 class="popup-heading">Signup Successful!</h3>
      <p class="popup-description">All set to go. You’ll now receive personalized job alerts based on your interests and location.</p>
      <button id="closeSignupPopupButton">Close</button>
    </div>

    <div id="popupLoginSuccess" class="popup" style="display:none;">
      <img class="popup-image-pc-and-mobile" src="https://findjobsinfinland.fi/images/sucessfully.png" alt="Login Success">
      <h3 class="popup-heading">Login Successful!</h3>
      <p class="popup-description">Welcome back. You’ll now receive personalized job alerts based on your interests and location.</p>
      <button id="closeLoginPopupButton">Close</button>
    </div>
  `;

container.appendChild(wrapper);




async function loadPopupOptions() {
  try {
    const catRes = await fetch('/scraper/all_jobs_cat.json');
    if (!catRes.ok) throw new Error('Failed to fetch categories');
    const catData = await catRes.json();
    const categories = catData.categories || [];

    function slugToDisplay(slug) {
      return slug.split('-').map(w => {
        if (w.toLowerCase() === 'it') return 'IT';
        if (['and', 'of', 'the'].includes(w.toLowerCase())) return w.toLowerCase();
        return w.charAt(0).toUpperCase() + w.slice(1);
      }).join(' ');
    }

    let catHtml = '<div class="option-row"><span>All Categories</span><label class="switch"><input type="checkbox" value="all-categories" /><span class="slider"></span></label></div>';
    categories.forEach(slug => {
      catHtml += `<div class="option-row"><span>${slugToDisplay(slug)}</span><label class="switch"><input type="checkbox" value="${slug}" /><span class="slider"></span></label></div>`;
    });

    const catBox = document.getElementById('categoryBox');
    if (catBox) catBox.innerHTML = catHtml;

    const locRes = await fetch('/scraper/all_jobs_loc.json');
    if (!locRes.ok) throw new Error('Failed to fetch locations');
    const locData = await locRes.json();

    let locHtml = '<div class="option-row"><span>All Locations</span><label class="switch"><input type="checkbox" value="all-location" /><span class="slider"></span></label></div>';
    for (const [region, cities] of Object.entries(locData)) {
      const regionSlug = region.toLowerCase();
      locHtml += `<div class="option-row region-header"><span>${region}</span><label class="switch"><input type="checkbox" value="${regionSlug}" /><span class="slider"></span></label></div>`;
      const sortedCities = [...cities].sort();
      sortedCities.forEach(city => {
        const citySlug = city.toLowerCase();
        locHtml += `<div class="option-row"><span>${city}</span><label class="switch"><input type="checkbox" value="${citySlug}" /><span class="slider"></span></label></div>`;
      });
    }

    const locBox = document.getElementById('locationBox');
    if (locBox) locBox.innerHTML = locHtml;

  } catch (e) {
    console.error("Error loading popup options:", e);
  }
}
loadPopupOptions();
