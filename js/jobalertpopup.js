

const jobAlertContainer = document.getElementById("job-alert-popup-content");

const jobAlertPopup = document.createElement("div");
jobAlertPopup.id = "jobAlertPopup";
jobAlertPopup.style.display = "none";

jobAlertPopup.innerHTML = `
    <div class="popup-content-unique" id="popupStep1" style="display:none;">
      <h3 class="popup-heading-unique">Want to get Personalised Job alerts?</h3>
      <img src="http://findjobsinfinland.fi/images/job-alert.png" class="popup-image-mobile-unique" alt="Job Alert" />
      <p class="popup-description-for-pc-unique">
        We’ll securely save your job preferences and notify you instantly via email and push
        notifications whenever new job postings match your selected interests, categories, or
        preferred locations. <br><br> Stay ahead and never miss an opportunity that fits your career goals.
      </p>
      <p class="popup-description-for-mobile-unique">
        We’ll save your job preferences and notify you instantly via email and notifications about new
        job postings that match your preferences.
      </p>
      <div class="popup-buttons-unique">
        <button class="yes-btn-unique" onclick="handlePopupYes(); clickLabelOnYes()">Yes</button>
        <button class="no-btn-unique" onclick="handlePopupNo()">No</button>
      </div>
    </div>

    <div class="popup-content-unique" id="popupStep1b" style="display:none;">
      <h3 class="popup-heading-unique">Oops! Did you pressed ‘No’ by mistake?</h3>
      <img src="http://findjobsinfinland.fi/images/second-step.png" class="popup-image-mobile-unique" alt="No Notifications" />
      <p class="popup-description-for-pc-unique">
        Since you pressed ‘No’, you will not receive notifications about new job opportunities that
        match your interests. When enabled, we instantly alert you via email and notifications whenever
        relevant jobs are posted. <br><br> Without job alerts, you might miss out on awesome
        opportunities perfectly matched to you. So, Lets stay ahead — enable alerts to never miss an
        opportunity.
      </p>
      <p class="popup-description-for-mobile-unique">
        Since you pressed ‘No’, you won’t get notifications about new jobs matching your interests.
        Would you like us to notify you instantly via email and notifications?
      </p>
      <div class="finalbuttons-unique">
        <button class="yesbtn-unique" onclick="handleNoSkipAlerts()">No, skip alerts</button>
        <button class="nobtn-unique" onclick="handlePopupYes(); clickLabelOnYes()">Yes, notify me</button>
      </div>
    </div>

    <div class="popup-content-unique" id="popupStep1c" style="display:none;">
      <h3 class="popup-heading-unique">Are you sure you don't want to get job alerts?</h3>
      <img src="http://findjobsinfinland.fi/images/last-step.png" class="popup-image-mobile-unique" alt="Last Step" />
      <p class="popup-description-for-pc-unique">
        One last step to re-consider. By skipping this, you won’t receive timely notifications about
        new jobs tailored specifically to your interests and skills.<br><br> You still have a chance to go
        back if you change your mind.<br><br>
      </p>
      <p class="popup-description-for-mobile-unique">
        If you skip this, you won’t receive timely alerts about jobs tailored to your interests and
        skills. You can still go back now if you’ve changed your mind.
        <br><br>
      </p>
      <label class="toggle-label-unique" for="neverShowAgainToggle">
        Never show this message again
        <span class="toggle-switch-unique">
          <input type="checkbox" id="neverShowAgainToggle" />
          <span class="slider-unique"></span>
        </span>
      </label>
      <div class="finalbuttons-unique">
        <button class="yesbtn-unique" onclick="confirmFinalNo(true)">Yes, I’m sure</button>
        <button class="nobtn-unique" onclick="handlePopupYes(); clickLabelOnYes()">No, go back</button>
      </div>
    </div>

    <div class="popup-content-unique" id="popupBlockedNotifications" style="display:none;">
      <h3 class="popup-heading-unique" id="headingBlockedNotifications">Did you accidentally blocked notifications?</h3>
      <p class="popup-description-unique popdesc" id="descriptionPCBlockedNotifications">
        If it was a mistake, and notifications are disabled, then fix it. If notifications are not
        enabled, you will not receive personalized job alerts based on your
        interests and locations. <br><br>
        If you're overwhelmed by notifications and prefer to only receive updates via email, you can
        opt for email notifications instead.
      </p>
      <div class="finalbuttons-unique" id="buttonsBlockedNotifications">
        <button class="blockedbuttons yesbtn-unique" id="yesButtonBlockedNotifications">Yes, I only want
          email notifications</button>
        <button class="blockedbuttons nobtn-unique" id="noButtonBlockedNotifications">No, I want to enable
          notifications</button>
      </div>
    </div>

    <div class="popup-content-unique" id="popupEnableNotifications" style="display:none;">
      <h3 class="popup-heading-unique" id="headingEnableNotifications">Re-enable Job alert Notifications</h3>
      <p class="popup-description-for-pc-unique blockeddescription" id="descriptionPCEnableNotifications">
        If you’d like to start receiving personalized job alerts and updates in real time, you’ll need
        to re-enable browser notifications for this site. It’s quick and easy—just follow the steps
        below:
      </p>
      <p class="popup-description-for-mobile-unique blockeddescription" id="descriptionPCEnableNotifications">
        If you'd like to re-enable notifications to start receiving personalized job alerts and
        updates, follow these steps:
      </p>
      <ol class="steps-list-mobile">
        <li id="step1Enable">
          Click the &nbsp;
          <svg class="icon inline-icon" xmlns="http://www.w3.org/2000/svg" version="1.0" width="20px"
            height="20px" viewBox="0 0 512.000000 512.000000" preserveAspectRatio="xMidYMid meet">
            <g transform="translate(0.000000,512.000000) scale(0.100000,-0.100000)" stroke="none">
              <path d="M1490 4365 c-197 -40 -378 -147 -498 -295 -59 -73 -134 -213 -157 -292 l-16 -58 -333 0 -332 0 -50 -25 c-75 -38 -99 -80 -99 -175 0 -95 24 -137 99 -175 l50 -25 332 0 333 0 16 -57 c22 -79 94 -212 155 -289 85 -106 219 -202 356 -255 240 -92 512 -72 739 56 83 46 185 133 245 208 56 70 133 218 151 290 l11 47 1238 0 1238 0 53 28 c39 20 58 38 76 71 27 51 31 133 9 184 -17 41 -66 88 -108 104 -25 8 -346 12 -1268 12 l-1235 1 -23 72 c-70 222 -260 430 -475 521 -147 61 -355 83 -507 52z m365 -440 c92 -44 166 -118 213 -214 36 -74 37 -77 37 -190 -1 -139 -19 -194 -92 -286 -55 -67 -119 -114 -201 -147 -81 -32 -232 -32 -314 1 -302 118 -394 495 -179 734 134 149 354 191 536 102z" />
              <path d="M3310 2446 c-183 -34 -324 -111 -456 -247 -104 -108 -163 -206 -203 -339 l-17 -55 -1250 -5 c-903 -4 -1256 -8 -1274 -16 -38 -17 -88 -73 -101 -112 -6 -19 -9 -60 -7 -92 5 -73 36 -120 99 -155 l47 -25 1238 0 1239 0 23 -71 c108 -344 449 -589 818 -589 248 0 514 126 665 316 60 75 131 209 154 289 l16 55 337 0 337 0 51 30 c64 36 94 91 94 168 0 63 -17 107 -56 145 -55 55 -67 57 -430 57 l-333 0 -16 55 c-22 77 -92 209 -149 284 -109 142 -307 264 -487 301 -106 22 -239 24 -339 6z m252 -397 c246 -53 408 -299 354 -542 -27 -121 -94 -219 -194 -284 -197 -128 -462 -88 -605 91 -83 105 -119 237 -97 358 46 259 293 430 542 377z" />
            </g>
          </svg>
          &nbsp; icon next to the website link in the address bar.
        </li>
        <li id="step2Enable">Select <strong>"Permissions"</strong> & Click on <strong>"Reset Permissions"</strong></li>
        <li id="step3Enable">Press <strong>"Reset"</strong> and refresh the page.</li>
      </ol>
      <button class="blockclosebtn">Close</sbutton>
    </div>
  `;

jobAlertContainer.appendChild(jobAlertPopup);








