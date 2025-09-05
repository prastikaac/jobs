
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
      <h3 class="popup-heading lasthead">Select Job & Location</h3>
      <p class="popup-description" style="margin-top:-2px; margin-bottom:25px;">
        Choose the types of jobs you're interested in and the locations where you'd like to work.
      </p>

      <h3>I. What kind of jobs are you interested in?</h3>
      <div class="select-box" id="categoryBox">
     <div class="option-row"><span>All Categories</span><label class="switch"><input type="checkbox"
                        value="all-categories" /><span class="slider"></span></label></div>
                        <div class="option-row"><span>IT & Tech</span><label class="switch"><input type="checkbox" value="it-tech" /><span class="slider"></span></label></div>
<div class="option-row"><span>Engineering</span><label class="switch"><input type="checkbox" value="engineering" /><span class="slider"></span></label></div>
<div class="option-row"><span>Nursing</span><label class="switch"><input type="checkbox" value="nursing" /><span class="slider"></span></label></div>
<div class="option-row"><span>Construction & Labor</span><label class="switch"><input type="checkbox" value="construction-labor" /><span class="slider"></span></label></div>
<div class="option-row"><span>Logistics & Delivery</span><label class="switch"><input type="checkbox" value="logistics-delivery" /><span class="slider"></span></label></div>
<div class="option-row"><span>Customer Service Support</span><label class="switch"><input type="checkbox" value="customer-service-support" /><span class="slider"></span></label></div>
<div class="option-row"><span>Internships & Traineeships</span><label class="switch"><input type="checkbox" value="internships-traineeships" /><span class="slider"></span></label></div>
<div class="option-row"><span>Cleaning</span><label class="switch"><input type="checkbox" value="cleaning" /><span class="slider"></span></label></div>
<div class="option-row"><span>Housekeeping</span><label class="switch"><input type="checkbox" value="housekeeping" /><span class="slider"></span></label></div>
<div class="option-row"><span>Cooking</span><label class="switch"><input type="checkbox" value="cooking" /><span class="slider"></span></label></div>
<div class="option-row"><span>Restaurant</span><label class="switch"><input type="checkbox" value="restaurant" /><span class="slider"></span></label></div>
<div class="option-row"><span>Hospitality & Service</span><label class="switch"><input type="checkbox" value="hospitality-service" /><span class="slider"></span></label></div>
<div class="option-row"><span>Caregiver</span><label class="switch"><input type="checkbox" value="caregiver" /><span class="slider"></span></label></div>
<div class="option-row"><span>Education & Teaching</span><label class="switch"><input type="checkbox" value="education-teaching" /><span class="slider"></span></label></div>
<div class="option-row"><span>Finance & Accounting</span><label class="switch"><input type="checkbox" value="finance-accounting" /><span class="slider"></span></label></div>
<div class="option-row"><span>Sales & Marketing</span><label class="switch"><input type="checkbox" value="sales-marketing" /><span class="slider"></span></label></div>

        </div>
        <div id="categoryError" class="error-message"></div>

      <h3>II. Where do you want to work?</h3>
      <div class="select-box" id="locationBox">
         <div class="option-row"><span>All Locations</span><label class="switch"><input type="checkbox"
                        value="all-location" /><span class="slider"></span></label></div>
                        <div class="option-row">
  <span>Uusimaa Region</span>
  <label class="switch">
    <input type="checkbox" value="uusimaa-region" />
    <span class="slider"></span>
  </label>
</div>
<div class="option-row"><span>Helsinki</span><label class="switch"><input type="checkbox" value="helsinki" /><span class="slider"></span></label></div>
<div class="option-row"><span>Espoo</span><label class="switch"><input type="checkbox" value="espoo" /><span class="slider"></span></label></div>
<div class="option-row"><span>Vantaa</span><label class="switch"><input type="checkbox" value="vantaa" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kauniainen</span><label class="switch"><input type="checkbox" value="kauniainen" /><span class="slider"></span></label></div>
<div class="option-row"><span>Järvenpää</span><label class="switch"><input type="checkbox" value="jarvenpaa" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kerava</span><label class="switch"><input type="checkbox" value="kerava" /><span class="slider"></span></label></div>
<div class="option-row"><span>Tuusula</span><label class="switch"><input type="checkbox" value="tuusula" /><span class="slider"></span></label></div>
<div class="option-row"><span>Sipoo</span><label class="switch"><input type="checkbox" value="sipoo" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kirkkonummi</span><label class="switch"><input type="checkbox" value="kirkkonummi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Lohja</span><label class="switch"><input type="checkbox" value="lohja" /><span class="slider"></span></label></div>
<div class="option-row"><span>Nurmijärvi</span><label class="switch"><input type="checkbox" value="nurmijarvi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Hyvinkää</span><label class="switch"><input type="checkbox" value="hyvinkaa" /><span class="slider"></span></label></div>
<div class="option-row"><span>Inkoo</span><label class="switch"><input type="checkbox" value="inkoo" /><span class="slider"></span></label></div>
<div class="option-row"><span>Pasila</span><label class="switch"><input type="checkbox" value="pasila" /><span class="slider"></span></label></div>
<div class="option-row"><span>Malmi</span><label class="switch"><input type="checkbox" value="malmi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Tikkurila</span><label class="switch"><input type="checkbox" value="tikkurila" /><span class="slider"></span></label></div>
<div class="option-row"><span>Leppävaara</span><label class="switch"><input type="checkbox" value="leppavaara" /><span class="slider"></span></label></div>
<div class="option-row"><span>Matinkylä</span><label class="switch"><input type="checkbox" value="matinkyla" /><span class="slider"></span></label></div>
<div class="option-row"><span>Myyrmäki</span><label class="switch"><input type="checkbox" value="myyrmaki" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kamppi</span><label class="switch"><input type="checkbox" value="kamppi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kallio</span><label class="switch"><input type="checkbox" value="kallio" /><span class="slider"></span></label></div>
<div class="option-row"><span>Tapiola</span><label class="switch"><input type="checkbox" value="tapiola" /><span class="slider"></span></label></div>
<div class="option-row"><span>Itäkeskus</span><label class="switch"><input type="checkbox" value="itakeskus" /><span class="slider"></span></label></div>
<div class="option-row"><span>Lauttasaari</span><label class="switch"><input type="checkbox" value="lauttasaari" /><span class="slider"></span></label></div>
<div class="option-row"><span>Tampere</span><label class="switch"><input type="checkbox" value="tampere" /><span class="slider"></span></label></div>
<div class="option-row"><span>Turku</span><label class="switch"><input type="checkbox" value="turku" /><span class="slider"></span></label></div>
<div class="option-row"><span>Oulu</span><label class="switch"><input type="checkbox" value="oulu" /><span class="slider"></span></label></div>
<div class="option-row"><span>Jyväskylä</span><label class="switch"><input type="checkbox" value="jyvaskyla" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kuopio</span><label class="switch"><input type="checkbox" value="kuopio" /><span class="slider"></span></label></div>
<div class="option-row"><span>Lahti</span><label class="switch"><input type="checkbox" value="lahti" /><span class="slider"></span></label></div>
<div class="option-row"><span>Vaasa</span><label class="switch"><input type="checkbox" value="vaasa" /><span class="slider"></span></label></div>
<div class="option-row"><span>Seinäjoki</span><label class="switch"><input type="checkbox" value="seinajoki" /><span class="slider"></span></label></div>
<div class="option-row"><span>Rovaniemi</span><label class="switch"><input type="checkbox" value="rovaniemi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kotka</span><label class="switch"><input type="checkbox" value="kotka" /><span class="slider"></span></label></div>
<div class="option-row"><span>Lappeenranta</span><label class="switch"><input type="checkbox" value="lappeenranta" /><span class="slider"></span></label></div>
<div class="option-row"><span>Pori</span><label class="switch"><input type="checkbox" value="pori" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kokkola</span><label class="switch"><input type="checkbox" value="kokkola" /><span class="slider"></span></label></div>
<div class="option-row"><span>Joensuu</span><label class="switch"><input type="checkbox" value="joensuu" /><span class="slider"></span></label></div>

        </div>
        
        <div id="locationError" class="error-message"></div>
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
      <img class="popup-image-pc-and-mobile" src="http://findjobsinfinland.fi/images/sucessfully.png" alt="Signed Up Success">
      <h3 class="popup-heading">Signup Successful!</h3>
      <p class="popup-description">All set to go. You’ll now receive personalized job alerts based on your interests and location.</p>
      <button id="closeSignupPopupButton">Close</button>
    </div>

    <div id="popupLoginSuccess" class="popup" style="display:none;">
      <img class="popup-image-pc-and-mobile" src="http://findjobsinfinland.fi/images/sucessfully.png" alt="Login Success">
      <h3 class="popup-heading">Login Successful!</h3>
      <p class="popup-description">Welcome back. You’ll now receive personalized job alerts based on your interests and location.</p>
      <button id="closeLoginPopupButton">Close</button>
    </div>
  `;

container.appendChild(wrapper);


