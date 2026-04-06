
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
<div class="option-row"><span>All Categories</span><label class="switch"><input type="checkbox" value="all-categories" /><span class="slider"></span></label></div>
<div class="option-row"><span>IT and Tech</span><label class="switch"><input type="checkbox" value="it-and-tech" /><span class="slider"></span></label></div>
<div class="option-row"><span>Engineering and Technical</span><label class="switch"><input type="checkbox" value="engineering-and-technical" /><span class="slider"></span></label></div>
<div class="option-row"><span>Manufacturing and Production</span><label class="switch"><input type="checkbox" value="manufacturing-and-production" /><span class="slider"></span></label></div>
<div class="option-row"><span>Construction and Trades</span><label class="switch"><input type="checkbox" value="construction-and-trades" /><span class="slider"></span></label></div>
<div class="option-row"><span>Logistics and Transportation</span><label class="switch"><input type="checkbox" value="logistics-and-transportation" /><span class="slider"></span></label></div>
<div class="option-row"><span>Courier and Delivery</span><label class="switch"><input type="checkbox" value="courier-and-delivery" /><span class="slider"></span></label></div>
<div class="option-row"><span>Healthcare and Social Care</span><label class="switch"><input type="checkbox" value="healthcare-and-social-care" /><span class="slider"></span></label></div>
<div class="option-row"><span>Cleaning and Facility Services</span><label class="switch"><input type="checkbox" value="cleaning-and-facility-services" /><span class="slider"></span></label></div>
<div class="option-row"><span>Food and Restaurant</span><label class="switch"><input type="checkbox" value="food-and-restaurant" /><span class="slider"></span></label></div>
<div class="option-row"><span>Hospitality and Tourism</span><label class="switch"><input type="checkbox" value="hospitality-and-tourism" /><span class="slider"></span></label></div>
<div class="option-row"><span>Aviation</span><label class="switch"><input type="checkbox" value="aviation" /><span class="slider"></span></label></div>
<div class="option-row"><span>Customer Service and Retail</span><label class="switch"><input type="checkbox" value="customer-service-and-retail" /><span class="slider"></span></label></div>
<div class="option-row"><span>Business and Finance</span><label class="switch"><input type="checkbox" value="business-and-finance" /><span class="slider"></span></label></div>
<div class="option-row"><span>Professional Services</span><label class="switch"><input type="checkbox" value="professional-services" /><span class="slider"></span></label></div>
<div class="option-row"><span>Administrative and Support Services</span><label class="switch"><input type="checkbox" value="administrative-and-support-services" /><span class="slider"></span></label></div>
<div class="option-row"><span>Education and Public Sector</span><label class="switch"><input type="checkbox" value="education-and-public-sector" /><span class="slider"></span></label></div>
<div class="option-row"><span>Government and Public Services</span><label class="switch"><input type="checkbox" value="government-and-public-services" /><span class="slider"></span></label></div>
<div class="option-row"><span>Law and Legal</span><label class="switch"><input type="checkbox" value="law-and-legal" /><span class="slider"></span></label></div>
<div class="option-row"><span>Creative and Media</span><label class="switch"><input type="checkbox" value="creative-and-media" /><span class="slider"></span></label></div>
<div class="option-row"><span>Arts and Entertainment</span><label class="switch"><input type="checkbox" value="arts-and-entertainment" /><span class="slider"></span></label></div>
<div class="option-row"><span>Gaming and Esports</span><label class="switch"><input type="checkbox" value="gaming-and-esports" /><span class="slider"></span></label></div>
<div class="option-row"><span>Scientific and Research</span><label class="switch"><input type="checkbox" value="scientific-and-research" /><span class="slider"></span></label></div>
<div class="option-row"><span>Lifestyle and Wellness</span><label class="switch"><input type="checkbox" value="lifestyle-and-wellness" /><span class="slider"></span></label></div>
<div class="option-row"><span>Agriculture and Environment</span><label class="switch"><input type="checkbox" value="agriculture-and-environment" /><span class="slider"></span></label></div>
<div class="option-row"><span>Energy and Utilities</span><label class="switch"><input type="checkbox" value="energy-and-utilities" /><span class="slider"></span></label></div>
<div class="option-row"><span>Security and Safety</span><label class="switch"><input type="checkbox" value="security-and-safety" /><span class="slider"></span></label></div>
<div class="option-row"><span>Automotive and Maintenance</span><label class="switch"><input type="checkbox" value="automotive-and-maintenance" /><span class="slider"></span></label></div>
<div class="option-row"><span>Travel and Tourism</span><label class="switch"><input type="checkbox" value="travel-and-tourism" /><span class="slider"></span></label></div>
<div class="option-row"><span>Flexible and Entry Level</span><label class="switch"><input type="checkbox" value="flexible-and-entry-level" /><span class="slider"></span></label></div>
<div class="option-row"><span>Other</span><label class="switch"><input type="checkbox" value="other" /><span class="slider"></span></label></div>
        </div>
        <div id="categoryError" class="error-message"></div>

      <h3>II. Where do you want to work?</h3>
      <div class="select-box" id="locationBox">
<div class="option-row"><span>All Locations</span><label class="switch"><input type="checkbox" value="all-location" /><span class="slider"></span></label></div>
<div class="option-row region-header"><span>Uusimaa</span><label class="switch"><input type="checkbox" value="uusimaa" /><span class="slider"></span></label></div>
<div class="option-row"><span>Askola</span><label class="switch"><input type="checkbox" value="askola" /><span class="slider"></span></label></div>
<div class="option-row"><span>Espoo</span><label class="switch"><input type="checkbox" value="espoo" /><span class="slider"></span></label></div>
<div class="option-row"><span>Hanko</span><label class="switch"><input type="checkbox" value="hanko" /><span class="slider"></span></label></div>
<div class="option-row"><span>Helsinki</span><label class="switch"><input type="checkbox" value="helsinki" /><span class="slider"></span></label></div>
<div class="option-row"><span>Hyvinkää</span><label class="switch"><input type="checkbox" value="hyvinkää" /><span class="slider"></span></label></div>
<div class="option-row"><span>Inkoo</span><label class="switch"><input type="checkbox" value="inkoo" /><span class="slider"></span></label></div>
<div class="option-row"><span>Järvenpää</span><label class="switch"><input type="checkbox" value="järvenpää" /><span class="slider"></span></label></div>
<div class="option-row"><span>Karkkila</span><label class="switch"><input type="checkbox" value="karkkila" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kauniainen</span><label class="switch"><input type="checkbox" value="kauniainen" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kerava</span><label class="switch"><input type="checkbox" value="kerava" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kirkkonummi</span><label class="switch"><input type="checkbox" value="kirkkonummi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Lapinjärvi</span><label class="switch"><input type="checkbox" value="lapinjärvi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Lohja</span><label class="switch"><input type="checkbox" value="lohja" /><span class="slider"></span></label></div>
<div class="option-row"><span>Loviisa</span><label class="switch"><input type="checkbox" value="loviisa" /><span class="slider"></span></label></div>
<div class="option-row"><span>Myrskylä</span><label class="switch"><input type="checkbox" value="myrskylä" /><span class="slider"></span></label></div>
<div class="option-row"><span>Mäntsälä</span><label class="switch"><input type="checkbox" value="mäntsälä" /><span class="slider"></span></label></div>
<div class="option-row"><span>Nurmijärvi</span><label class="switch"><input type="checkbox" value="nurmijärvi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Pornainen</span><label class="switch"><input type="checkbox" value="pornainen" /><span class="slider"></span></label></div>
<div class="option-row"><span>Porvoo</span><label class="switch"><input type="checkbox" value="porvoo" /><span class="slider"></span></label></div>
<div class="option-row"><span>Pukkila</span><label class="switch"><input type="checkbox" value="pukkila" /><span class="slider"></span></label></div>
<div class="option-row"><span>Raasepori</span><label class="switch"><input type="checkbox" value="raasepori" /><span class="slider"></span></label></div>
<div class="option-row"><span>Sipoo</span><label class="switch"><input type="checkbox" value="sipoo" /><span class="slider"></span></label></div>
<div class="option-row"><span>Siuntio</span><label class="switch"><input type="checkbox" value="siuntio" /><span class="slider"></span></label></div>
<div class="option-row"><span>Tuusula</span><label class="switch"><input type="checkbox" value="tuusula" /><span class="slider"></span></label></div>
<div class="option-row"><span>Vantaa</span><label class="switch"><input type="checkbox" value="vantaa" /><span class="slider"></span></label></div>
<div class="option-row"><span>Vihti</span><label class="switch"><input type="checkbox" value="vihti" /><span class="slider"></span></label></div>
<div class="option-row region-header"><span>Southwest Finland</span><label class="switch"><input type="checkbox" value="southwest finland" /><span class="slider"></span></label></div>
<div class="option-row"><span>Aura</span><label class="switch"><input type="checkbox" value="aura" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kaarina</span><label class="switch"><input type="checkbox" value="kaarina" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kemiönsaari</span><label class="switch"><input type="checkbox" value="kemiönsaari" /><span class="slider"></span></label></div>
<div class="option-row"><span>Koski Tl</span><label class="switch"><input type="checkbox" value="koski tl" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kustavi</span><label class="switch"><input type="checkbox" value="kustavi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Laitila</span><label class="switch"><input type="checkbox" value="laitila" /><span class="slider"></span></label></div>
<div class="option-row"><span>Lieto</span><label class="switch"><input type="checkbox" value="lieto" /><span class="slider"></span></label></div>
<div class="option-row"><span>Loimaa</span><label class="switch"><input type="checkbox" value="loimaa" /><span class="slider"></span></label></div>
<div class="option-row"><span>Marttila</span><label class="switch"><input type="checkbox" value="marttila" /><span class="slider"></span></label></div>
<div class="option-row"><span>Masku</span><label class="switch"><input type="checkbox" value="masku" /><span class="slider"></span></label></div>
<div class="option-row"><span>Mynämäki</span><label class="switch"><input type="checkbox" value="mynämäki" /><span class="slider"></span></label></div>
<div class="option-row"><span>Naantali</span><label class="switch"><input type="checkbox" value="naantali" /><span class="slider"></span></label></div>
<div class="option-row"><span>Nousiainen</span><label class="switch"><input type="checkbox" value="nousiainen" /><span class="slider"></span></label></div>
<div class="option-row"><span>Oripää</span><label class="switch"><input type="checkbox" value="oripää" /><span class="slider"></span></label></div>
<div class="option-row"><span>Paimio</span><label class="switch"><input type="checkbox" value="paimio" /><span class="slider"></span></label></div>
<div class="option-row"><span>Parainen</span><label class="switch"><input type="checkbox" value="parainen" /><span class="slider"></span></label></div>
<div class="option-row"><span>Pyhäranta</span><label class="switch"><input type="checkbox" value="pyhäranta" /><span class="slider"></span></label></div>
<div class="option-row"><span>Pöytyä</span><label class="switch"><input type="checkbox" value="pöytyä" /><span class="slider"></span></label></div>
<div class="option-row"><span>Raisio</span><label class="switch"><input type="checkbox" value="raisio" /><span class="slider"></span></label></div>
<div class="option-row"><span>Rusko</span><label class="switch"><input type="checkbox" value="rusko" /><span class="slider"></span></label></div>
<div class="option-row"><span>Salo</span><label class="switch"><input type="checkbox" value="salo" /><span class="slider"></span></label></div>
<div class="option-row"><span>Sauvo</span><label class="switch"><input type="checkbox" value="sauvo" /><span class="slider"></span></label></div>
<div class="option-row"><span>Somero</span><label class="switch"><input type="checkbox" value="somero" /><span class="slider"></span></label></div>
<div class="option-row"><span>Taivassalo</span><label class="switch"><input type="checkbox" value="taivassalo" /><span class="slider"></span></label></div>
<div class="option-row"><span>Turku</span><label class="switch"><input type="checkbox" value="turku" /><span class="slider"></span></label></div>
<div class="option-row"><span>Uusikaupunki</span><label class="switch"><input type="checkbox" value="uusikaupunki" /><span class="slider"></span></label></div>
<div class="option-row"><span>Vehmaa</span><label class="switch"><input type="checkbox" value="vehmaa" /><span class="slider"></span></label></div>
<div class="option-row region-header"><span>South Karelia</span><label class="switch"><input type="checkbox" value="south karelia" /><span class="slider"></span></label></div>
<div class="option-row"><span>Imatra</span><label class="switch"><input type="checkbox" value="imatra" /><span class="slider"></span></label></div>
<div class="option-row"><span>Lappeenranta</span><label class="switch"><input type="checkbox" value="lappeenranta" /><span class="slider"></span></label></div>
<div class="option-row"><span>Lemi</span><label class="switch"><input type="checkbox" value="lemi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Luumäki</span><label class="switch"><input type="checkbox" value="luumäki" /><span class="slider"></span></label></div>
<div class="option-row"><span>Parikkala</span><label class="switch"><input type="checkbox" value="parikkala" /><span class="slider"></span></label></div>
<div class="option-row"><span>Rautjärvi</span><label class="switch"><input type="checkbox" value="rautjärvi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Ruokolahti</span><label class="switch"><input type="checkbox" value="ruokolahti" /><span class="slider"></span></label></div>
<div class="option-row"><span>Savitaipale</span><label class="switch"><input type="checkbox" value="savitaipale" /><span class="slider"></span></label></div>
<div class="option-row"><span>Taipalsaari</span><label class="switch"><input type="checkbox" value="taipalsaari" /><span class="slider"></span></label></div>
<div class="option-row region-header"><span>Kanta-Häme</span><label class="switch"><input type="checkbox" value="kanta-häme" /><span class="slider"></span></label></div>
<div class="option-row"><span>Forssa</span><label class="switch"><input type="checkbox" value="forssa" /><span class="slider"></span></label></div>
<div class="option-row"><span>Hattula</span><label class="switch"><input type="checkbox" value="hattula" /><span class="slider"></span></label></div>
<div class="option-row"><span>Hausjärvi</span><label class="switch"><input type="checkbox" value="hausjärvi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Humppila</span><label class="switch"><input type="checkbox" value="humppila" /><span class="slider"></span></label></div>
<div class="option-row"><span>Hämeenlinna</span><label class="switch"><input type="checkbox" value="hämeenlinna" /><span class="slider"></span></label></div>
<div class="option-row"><span>Janakkala</span><label class="switch"><input type="checkbox" value="janakkala" /><span class="slider"></span></label></div>
<div class="option-row"><span>Jokioinen</span><label class="switch"><input type="checkbox" value="jokioinen" /><span class="slider"></span></label></div>
<div class="option-row"><span>Loppi</span><label class="switch"><input type="checkbox" value="loppi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Riihimäki</span><label class="switch"><input type="checkbox" value="riihimäki" /><span class="slider"></span></label></div>
<div class="option-row"><span>Tammela</span><label class="switch"><input type="checkbox" value="tammela" /><span class="slider"></span></label></div>
<div class="option-row"><span>Ypäjä</span><label class="switch"><input type="checkbox" value="ypäjä" /><span class="slider"></span></label></div>
<div class="option-row region-header"><span>Päijät-Häme</span><label class="switch"><input type="checkbox" value="päijät-häme" /><span class="slider"></span></label></div>
<div class="option-row"><span>Asikkala</span><label class="switch"><input type="checkbox" value="asikkala" /><span class="slider"></span></label></div>
<div class="option-row"><span>Hartola</span><label class="switch"><input type="checkbox" value="hartola" /><span class="slider"></span></label></div>
<div class="option-row"><span>Heinola</span><label class="switch"><input type="checkbox" value="heinola" /><span class="slider"></span></label></div>
<div class="option-row"><span>Hollola</span><label class="switch"><input type="checkbox" value="hollola" /><span class="slider"></span></label></div>
<div class="option-row"><span>Iitti</span><label class="switch"><input type="checkbox" value="iitti" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kärkölä</span><label class="switch"><input type="checkbox" value="kärkölä" /><span class="slider"></span></label></div>
<div class="option-row"><span>Lahti</span><label class="switch"><input type="checkbox" value="lahti" /><span class="slider"></span></label></div>
<div class="option-row"><span>Orimattila</span><label class="switch"><input type="checkbox" value="orimattila" /><span class="slider"></span></label></div>
<div class="option-row"><span>Padasjoki</span><label class="switch"><input type="checkbox" value="padasjoki" /><span class="slider"></span></label></div>
<div class="option-row"><span>Sysmä</span><label class="switch"><input type="checkbox" value="sysmä" /><span class="slider"></span></label></div>
<div class="option-row region-header"><span>Kymenlaakso</span><label class="switch"><input type="checkbox" value="kymenlaakso" /><span class="slider"></span></label></div>
<div class="option-row"><span>Hamina</span><label class="switch"><input type="checkbox" value="hamina" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kotka</span><label class="switch"><input type="checkbox" value="kotka" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kouvola</span><label class="switch"><input type="checkbox" value="kouvola" /><span class="slider"></span></label></div>
<div class="option-row"><span>Miehikkälä</span><label class="switch"><input type="checkbox" value="miehikkälä" /><span class="slider"></span></label></div>
<div class="option-row"><span>Pyhtää</span><label class="switch"><input type="checkbox" value="pyhtää" /><span class="slider"></span></label></div>
<div class="option-row"><span>Virolahti</span><label class="switch"><input type="checkbox" value="virolahti" /><span class="slider"></span></label></div>
<div class="option-row region-header"><span>South Ostrobothnia</span><label class="switch"><input type="checkbox" value="south ostrobothnia" /><span class="slider"></span></label></div>
<div class="option-row"><span>Alajärvi</span><label class="switch"><input type="checkbox" value="alajärvi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Alavus</span><label class="switch"><input type="checkbox" value="alavus" /><span class="slider"></span></label></div>
<div class="option-row"><span>Evijärvi</span><label class="switch"><input type="checkbox" value="evijärvi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Ilmajoki</span><label class="switch"><input type="checkbox" value="ilmajoki" /><span class="slider"></span></label></div>
<div class="option-row"><span>Isojoki</span><label class="switch"><input type="checkbox" value="isojoki" /><span class="slider"></span></label></div>
<div class="option-row"><span>Isokyrö</span><label class="switch"><input type="checkbox" value="isokyrö" /><span class="slider"></span></label></div>
<div class="option-row"><span>Karijoki</span><label class="switch"><input type="checkbox" value="karijoki" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kauhajoki</span><label class="switch"><input type="checkbox" value="kauhajoki" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kauhava</span><label class="switch"><input type="checkbox" value="kauhava" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kuortane</span><label class="switch"><input type="checkbox" value="kuortane" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kurikka</span><label class="switch"><input type="checkbox" value="kurikka" /><span class="slider"></span></label></div>
<div class="option-row"><span>Lappajärvi</span><label class="switch"><input type="checkbox" value="lappajärvi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Lapua</span><label class="switch"><input type="checkbox" value="lapua" /><span class="slider"></span></label></div>
<div class="option-row"><span>Seinäjoki</span><label class="switch"><input type="checkbox" value="seinäjoki" /><span class="slider"></span></label></div>
<div class="option-row"><span>Soini</span><label class="switch"><input type="checkbox" value="soini" /><span class="slider"></span></label></div>
<div class="option-row"><span>Teuva</span><label class="switch"><input type="checkbox" value="teuva" /><span class="slider"></span></label></div>
<div class="option-row"><span>Vimpeli</span><label class="switch"><input type="checkbox" value="vimpeli" /><span class="slider"></span></label></div>
<div class="option-row"><span>Ähtäri</span><label class="switch"><input type="checkbox" value="ähtäri" /><span class="slider"></span></label></div>
<div class="option-row region-header"><span>Central Finland</span><label class="switch"><input type="checkbox" value="central finland" /><span class="slider"></span></label></div>
<div class="option-row"><span>Hankasalmi</span><label class="switch"><input type="checkbox" value="hankasalmi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Joutsa</span><label class="switch"><input type="checkbox" value="joutsa" /><span class="slider"></span></label></div>
<div class="option-row"><span>Jyväskylä</span><label class="switch"><input type="checkbox" value="jyväskylä" /><span class="slider"></span></label></div>
<div class="option-row"><span>Jämsä</span><label class="switch"><input type="checkbox" value="jämsä" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kannonkoski</span><label class="switch"><input type="checkbox" value="kannonkoski" /><span class="slider"></span></label></div>
<div class="option-row"><span>Karstula</span><label class="switch"><input type="checkbox" value="karstula" /><span class="slider"></span></label></div>
<div class="option-row"><span>Keuruu</span><label class="switch"><input type="checkbox" value="keuruu" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kinnula</span><label class="switch"><input type="checkbox" value="kinnula" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kivijärvi</span><label class="switch"><input type="checkbox" value="kivijärvi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Konnevesi</span><label class="switch"><input type="checkbox" value="konnevesi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kyyjärvi</span><label class="switch"><input type="checkbox" value="kyyjärvi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Laukaa</span><label class="switch"><input type="checkbox" value="laukaa" /><span class="slider"></span></label></div>
<div class="option-row"><span>Luhanka</span><label class="switch"><input type="checkbox" value="luhanka" /><span class="slider"></span></label></div>
<div class="option-row"><span>Multia</span><label class="switch"><input type="checkbox" value="multia" /><span class="slider"></span></label></div>
<div class="option-row"><span>Muurame</span><label class="switch"><input type="checkbox" value="muurame" /><span class="slider"></span></label></div>
<div class="option-row"><span>Petäjävesi</span><label class="switch"><input type="checkbox" value="petäjävesi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Pihtipudas</span><label class="switch"><input type="checkbox" value="pihtipudas" /><span class="slider"></span></label></div>
<div class="option-row"><span>Saarijärvi</span><label class="switch"><input type="checkbox" value="saarijärvi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Toivakka</span><label class="switch"><input type="checkbox" value="toivakka" /><span class="slider"></span></label></div>
<div class="option-row"><span>Uurainen</span><label class="switch"><input type="checkbox" value="uurainen" /><span class="slider"></span></label></div>
<div class="option-row"><span>Viitasaari</span><label class="switch"><input type="checkbox" value="viitasaari" /><span class="slider"></span></label></div>
<div class="option-row"><span>Äänekoski</span><label class="switch"><input type="checkbox" value="äänekoski" /><span class="slider"></span></label></div>
<div class="option-row region-header"><span>Pirkanmaa</span><label class="switch"><input type="checkbox" value="pirkanmaa" /><span class="slider"></span></label></div>
<div class="option-row"><span>Akaa</span><label class="switch"><input type="checkbox" value="akaa" /><span class="slider"></span></label></div>
<div class="option-row"><span>Hämeenkyrö</span><label class="switch"><input type="checkbox" value="hämeenkyrö" /><span class="slider"></span></label></div>
<div class="option-row"><span>Ikaalinen</span><label class="switch"><input type="checkbox" value="ikaalinen" /><span class="slider"></span></label></div>
<div class="option-row"><span>Juupajoki</span><label class="switch"><input type="checkbox" value="juupajoki" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kangasala</span><label class="switch"><input type="checkbox" value="kangasala" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kihniö</span><label class="switch"><input type="checkbox" value="kihniö" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kuhmoinen</span><label class="switch"><input type="checkbox" value="kuhmoinen" /><span class="slider"></span></label></div>
<div class="option-row"><span>Lempäälä</span><label class="switch"><input type="checkbox" value="lempäälä" /><span class="slider"></span></label></div>
<div class="option-row"><span>Mänttä-Vilppula</span><label class="switch"><input type="checkbox" value="mänttä-vilppula" /><span class="slider"></span></label></div>
<div class="option-row"><span>Nokia</span><label class="switch"><input type="checkbox" value="nokia" /><span class="slider"></span></label></div>
<div class="option-row"><span>Orivesi</span><label class="switch"><input type="checkbox" value="orivesi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Parkano</span><label class="switch"><input type="checkbox" value="parkano" /><span class="slider"></span></label></div>
<div class="option-row"><span>Pirkkala</span><label class="switch"><input type="checkbox" value="pirkkala" /><span class="slider"></span></label></div>
<div class="option-row"><span>Punkalaidun</span><label class="switch"><input type="checkbox" value="punkalaidun" /><span class="slider"></span></label></div>
<div class="option-row"><span>Pälkäne</span><label class="switch"><input type="checkbox" value="pälkäne" /><span class="slider"></span></label></div>
<div class="option-row"><span>Ruovesi</span><label class="switch"><input type="checkbox" value="ruovesi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Sastamala</span><label class="switch"><input type="checkbox" value="sastamala" /><span class="slider"></span></label></div>
<div class="option-row"><span>Tampere</span><label class="switch"><input type="checkbox" value="tampere" /><span class="slider"></span></label></div>
<div class="option-row"><span>Urjala</span><label class="switch"><input type="checkbox" value="urjala" /><span class="slider"></span></label></div>
<div class="option-row"><span>Valkeakoski</span><label class="switch"><input type="checkbox" value="valkeakoski" /><span class="slider"></span></label></div>
<div class="option-row"><span>Vesilahti</span><label class="switch"><input type="checkbox" value="vesilahti" /><span class="slider"></span></label></div>
<div class="option-row"><span>Virrat</span><label class="switch"><input type="checkbox" value="virrat" /><span class="slider"></span></label></div>
<div class="option-row"><span>Ylöjärvi</span><label class="switch"><input type="checkbox" value="ylöjärvi" /><span class="slider"></span></label></div>
<div class="option-row region-header"><span>Ostrobothnia</span><label class="switch"><input type="checkbox" value="ostrobothnia" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kaskinen</span><label class="switch"><input type="checkbox" value="kaskinen" /><span class="slider"></span></label></div>
<div class="option-row"><span>Korsnäs</span><label class="switch"><input type="checkbox" value="korsnäs" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kristiinankaupunki</span><label class="switch"><input type="checkbox" value="kristiinankaupunki" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kruunupyy</span><label class="switch"><input type="checkbox" value="kruunupyy" /><span class="slider"></span></label></div>
<div class="option-row"><span>Laihia</span><label class="switch"><input type="checkbox" value="laihia" /><span class="slider"></span></label></div>
<div class="option-row"><span>Luoto</span><label class="switch"><input type="checkbox" value="luoto" /><span class="slider"></span></label></div>
<div class="option-row"><span>Maalahti</span><label class="switch"><input type="checkbox" value="maalahti" /><span class="slider"></span></label></div>
<div class="option-row"><span>Mustasaari</span><label class="switch"><input type="checkbox" value="mustasaari" /><span class="slider"></span></label></div>
<div class="option-row"><span>Närpiö</span><label class="switch"><input type="checkbox" value="närpiö" /><span class="slider"></span></label></div>
<div class="option-row"><span>Pedersöre</span><label class="switch"><input type="checkbox" value="pedersöre" /><span class="slider"></span></label></div>
<div class="option-row"><span>Pietarsaari</span><label class="switch"><input type="checkbox" value="pietarsaari" /><span class="slider"></span></label></div>
<div class="option-row"><span>Uusikaarlepyy</span><label class="switch"><input type="checkbox" value="uusikaarlepyy" /><span class="slider"></span></label></div>
<div class="option-row"><span>Vaasa</span><label class="switch"><input type="checkbox" value="vaasa" /><span class="slider"></span></label></div>
<div class="option-row"><span>Vöyri</span><label class="switch"><input type="checkbox" value="vöyri" /><span class="slider"></span></label></div>
<div class="option-row region-header"><span>Satakunta</span><label class="switch"><input type="checkbox" value="satakunta" /><span class="slider"></span></label></div>
<div class="option-row"><span>Eura</span><label class="switch"><input type="checkbox" value="eura" /><span class="slider"></span></label></div>
<div class="option-row"><span>Eurajoki</span><label class="switch"><input type="checkbox" value="eurajoki" /><span class="slider"></span></label></div>
<div class="option-row"><span>Harjavalta</span><label class="switch"><input type="checkbox" value="harjavalta" /><span class="slider"></span></label></div>
<div class="option-row"><span>Honkajoki</span><label class="switch"><input type="checkbox" value="honkajoki" /><span class="slider"></span></label></div>
<div class="option-row"><span>Huittinen</span><label class="switch"><input type="checkbox" value="huittinen" /><span class="slider"></span></label></div>
<div class="option-row"><span>Jämijärvi</span><label class="switch"><input type="checkbox" value="jämijärvi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kankaanpää</span><label class="switch"><input type="checkbox" value="kankaanpää" /><span class="slider"></span></label></div>
<div class="option-row"><span>Karvia</span><label class="switch"><input type="checkbox" value="karvia" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kokemäki</span><label class="switch"><input type="checkbox" value="kokemäki" /><span class="slider"></span></label></div>
<div class="option-row"><span>Merikarvia</span><label class="switch"><input type="checkbox" value="merikarvia" /><span class="slider"></span></label></div>
<div class="option-row"><span>Nakkila</span><label class="switch"><input type="checkbox" value="nakkila" /><span class="slider"></span></label></div>
<div class="option-row"><span>Pomarkku</span><label class="switch"><input type="checkbox" value="pomarkku" /><span class="slider"></span></label></div>
<div class="option-row"><span>Pori</span><label class="switch"><input type="checkbox" value="pori" /><span class="slider"></span></label></div>
<div class="option-row"><span>Rauma</span><label class="switch"><input type="checkbox" value="rauma" /><span class="slider"></span></label></div>
<div class="option-row"><span>Siikainen</span><label class="switch"><input type="checkbox" value="siikainen" /><span class="slider"></span></label></div>
<div class="option-row"><span>Säkylä</span><label class="switch"><input type="checkbox" value="säkylä" /><span class="slider"></span></label></div>
<div class="option-row"><span>Ulvila</span><label class="switch"><input type="checkbox" value="ulvila" /><span class="slider"></span></label></div>
<div class="option-row region-header"><span>Central Ostrobothnia</span><label class="switch"><input type="checkbox" value="central ostrobothnia" /><span class="slider"></span></label></div>
<div class="option-row"><span>Halsua</span><label class="switch"><input type="checkbox" value="halsua" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kannus</span><label class="switch"><input type="checkbox" value="kannus" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kaustinen</span><label class="switch"><input type="checkbox" value="kaustinen" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kokkola</span><label class="switch"><input type="checkbox" value="kokkola" /><span class="slider"></span></label></div>
<div class="option-row"><span>Lestijärvi</span><label class="switch"><input type="checkbox" value="lestijärvi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Perho</span><label class="switch"><input type="checkbox" value="perho" /><span class="slider"></span></label></div>
<div class="option-row"><span>Toholampi</span><label class="switch"><input type="checkbox" value="toholampi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Veteli</span><label class="switch"><input type="checkbox" value="veteli" /><span class="slider"></span></label></div>
<div class="option-row region-header"><span>North Savo</span><label class="switch"><input type="checkbox" value="north savo" /><span class="slider"></span></label></div>
<div class="option-row"><span>Iisalmi</span><label class="switch"><input type="checkbox" value="iisalmi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Joroinen</span><label class="switch"><input type="checkbox" value="joroinen" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kaavi</span><label class="switch"><input type="checkbox" value="kaavi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Keitele</span><label class="switch"><input type="checkbox" value="keitele" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kiuruvesi</span><label class="switch"><input type="checkbox" value="kiuruvesi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kuopio</span><label class="switch"><input type="checkbox" value="kuopio" /><span class="slider"></span></label></div>
<div class="option-row"><span>Lapinlahti</span><label class="switch"><input type="checkbox" value="lapinlahti" /><span class="slider"></span></label></div>
<div class="option-row"><span>Leppävirta</span><label class="switch"><input type="checkbox" value="leppävirta" /><span class="slider"></span></label></div>
<div class="option-row"><span>Pielavesi</span><label class="switch"><input type="checkbox" value="pielavesi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Rautalampi</span><label class="switch"><input type="checkbox" value="rautalampi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Rautavaara</span><label class="switch"><input type="checkbox" value="rautavaara" /><span class="slider"></span></label></div>
<div class="option-row"><span>Siilinjärvi</span><label class="switch"><input type="checkbox" value="siilinjärvi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Sonkajärvi</span><label class="switch"><input type="checkbox" value="sonkajärvi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Suonenjoki</span><label class="switch"><input type="checkbox" value="suonenjoki" /><span class="slider"></span></label></div>
<div class="option-row"><span>Tervo</span><label class="switch"><input type="checkbox" value="tervo" /><span class="slider"></span></label></div>
<div class="option-row"><span>Tuusniemi</span><label class="switch"><input type="checkbox" value="tuusniemi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Varkaus</span><label class="switch"><input type="checkbox" value="varkaus" /><span class="slider"></span></label></div>
<div class="option-row"><span>Vesanto</span><label class="switch"><input type="checkbox" value="vesanto" /><span class="slider"></span></label></div>
<div class="option-row"><span>Vieremä</span><label class="switch"><input type="checkbox" value="vieremä" /><span class="slider"></span></label></div>
<div class="option-row region-header"><span>North Ostrobothnia</span><label class="switch"><input type="checkbox" value="north ostrobothnia" /><span class="slider"></span></label></div>
<div class="option-row"><span>Alavieska</span><label class="switch"><input type="checkbox" value="alavieska" /><span class="slider"></span></label></div>
<div class="option-row"><span>Haapajärvi</span><label class="switch"><input type="checkbox" value="haapajärvi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Haapavesi</span><label class="switch"><input type="checkbox" value="haapavesi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Hailuoto</span><label class="switch"><input type="checkbox" value="hailuoto" /><span class="slider"></span></label></div>
<div class="option-row"><span>Ii</span><label class="switch"><input type="checkbox" value="ii" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kalajoki</span><label class="switch"><input type="checkbox" value="kalajoki" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kempele</span><label class="switch"><input type="checkbox" value="kempele" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kuusamo</span><label class="switch"><input type="checkbox" value="kuusamo" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kärsämäki</span><label class="switch"><input type="checkbox" value="kärsämäki" /><span class="slider"></span></label></div>
<div class="option-row"><span>Liminka</span><label class="switch"><input type="checkbox" value="liminka" /><span class="slider"></span></label></div>
<div class="option-row"><span>Lumijoki</span><label class="switch"><input type="checkbox" value="lumijoki" /><span class="slider"></span></label></div>
<div class="option-row"><span>Merijärvi</span><label class="switch"><input type="checkbox" value="merijärvi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Muhos</span><label class="switch"><input type="checkbox" value="muhos" /><span class="slider"></span></label></div>
<div class="option-row"><span>Nivala</span><label class="switch"><input type="checkbox" value="nivala" /><span class="slider"></span></label></div>
<div class="option-row"><span>Oulainen</span><label class="switch"><input type="checkbox" value="oulainen" /><span class="slider"></span></label></div>
<div class="option-row"><span>Oulu</span><label class="switch"><input type="checkbox" value="oulu" /><span class="slider"></span></label></div>
<div class="option-row"><span>Pudasjärvi</span><label class="switch"><input type="checkbox" value="pudasjärvi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Pyhäjoki</span><label class="switch"><input type="checkbox" value="pyhäjoki" /><span class="slider"></span></label></div>
<div class="option-row"><span>Pyhäjärvi</span><label class="switch"><input type="checkbox" value="pyhäjärvi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Pyhäntä</span><label class="switch"><input type="checkbox" value="pyhäntä" /><span class="slider"></span></label></div>
<div class="option-row"><span>Raahe</span><label class="switch"><input type="checkbox" value="raahe" /><span class="slider"></span></label></div>
<div class="option-row"><span>Reisjärvi</span><label class="switch"><input type="checkbox" value="reisjärvi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Sievi</span><label class="switch"><input type="checkbox" value="sievi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Siikajoki</span><label class="switch"><input type="checkbox" value="siikajoki" /><span class="slider"></span></label></div>
<div class="option-row"><span>Siikalatva</span><label class="switch"><input type="checkbox" value="siikalatva" /><span class="slider"></span></label></div>
<div class="option-row"><span>Taivalkoski</span><label class="switch"><input type="checkbox" value="taivalkoski" /><span class="slider"></span></label></div>
<div class="option-row"><span>Tyrnävä</span><label class="switch"><input type="checkbox" value="tyrnävä" /><span class="slider"></span></label></div>
<div class="option-row"><span>Utajärvi</span><label class="switch"><input type="checkbox" value="utajärvi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Vaala</span><label class="switch"><input type="checkbox" value="vaala" /><span class="slider"></span></label></div>
<div class="option-row"><span>Ylivieska</span><label class="switch"><input type="checkbox" value="ylivieska" /><span class="slider"></span></label></div>
<div class="option-row region-header"><span>Lapland</span><label class="switch"><input type="checkbox" value="lapland" /><span class="slider"></span></label></div>
<div class="option-row"><span>Enontekiö</span><label class="switch"><input type="checkbox" value="enontekiö" /><span class="slider"></span></label></div>
<div class="option-row"><span>Inari</span><label class="switch"><input type="checkbox" value="inari" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kemi</span><label class="switch"><input type="checkbox" value="kemi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kemijärvi</span><label class="switch"><input type="checkbox" value="kemijärvi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Keminmaa</span><label class="switch"><input type="checkbox" value="keminmaa" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kittilä</span><label class="switch"><input type="checkbox" value="kittilä" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kolari</span><label class="switch"><input type="checkbox" value="kolari" /><span class="slider"></span></label></div>
<div class="option-row"><span>Muonio</span><label class="switch"><input type="checkbox" value="muonio" /><span class="slider"></span></label></div>
<div class="option-row"><span>Pelkosenniemi</span><label class="switch"><input type="checkbox" value="pelkosenniemi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Pello</span><label class="switch"><input type="checkbox" value="pello" /><span class="slider"></span></label></div>
<div class="option-row"><span>Posio</span><label class="switch"><input type="checkbox" value="posio" /><span class="slider"></span></label></div>
<div class="option-row"><span>Ranua</span><label class="switch"><input type="checkbox" value="ranua" /><span class="slider"></span></label></div>
<div class="option-row"><span>Rovaniemi</span><label class="switch"><input type="checkbox" value="rovaniemi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Salla</span><label class="switch"><input type="checkbox" value="salla" /><span class="slider"></span></label></div>
<div class="option-row"><span>Savukoski</span><label class="switch"><input type="checkbox" value="savukoski" /><span class="slider"></span></label></div>
<div class="option-row"><span>Simo</span><label class="switch"><input type="checkbox" value="simo" /><span class="slider"></span></label></div>
<div class="option-row"><span>Sodankylä</span><label class="switch"><input type="checkbox" value="sodankylä" /><span class="slider"></span></label></div>
<div class="option-row"><span>Tervola</span><label class="switch"><input type="checkbox" value="tervola" /><span class="slider"></span></label></div>
<div class="option-row"><span>Tornio</span><label class="switch"><input type="checkbox" value="tornio" /><span class="slider"></span></label></div>
<div class="option-row"><span>Utsjoki</span><label class="switch"><input type="checkbox" value="utsjoki" /><span class="slider"></span></label></div>
<div class="option-row"><span>Ylitornio</span><label class="switch"><input type="checkbox" value="ylitornio" /><span class="slider"></span></label></div>
<div class="option-row region-header"><span>North Karelia</span><label class="switch"><input type="checkbox" value="north karelia" /><span class="slider"></span></label></div>
<div class="option-row"><span>Heinävesi</span><label class="switch"><input type="checkbox" value="heinävesi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Ilomantsi</span><label class="switch"><input type="checkbox" value="ilomantsi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Joensuu</span><label class="switch"><input type="checkbox" value="joensuu" /><span class="slider"></span></label></div>
<div class="option-row"><span>Juuka</span><label class="switch"><input type="checkbox" value="juuka" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kitee</span><label class="switch"><input type="checkbox" value="kitee" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kontiolahti</span><label class="switch"><input type="checkbox" value="kontiolahti" /><span class="slider"></span></label></div>
<div class="option-row"><span>Lieksa</span><label class="switch"><input type="checkbox" value="lieksa" /><span class="slider"></span></label></div>
<div class="option-row"><span>Liperi</span><label class="switch"><input type="checkbox" value="liperi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Nurmes</span><label class="switch"><input type="checkbox" value="nurmes" /><span class="slider"></span></label></div>
<div class="option-row"><span>Outokumpu</span><label class="switch"><input type="checkbox" value="outokumpu" /><span class="slider"></span></label></div>
<div class="option-row"><span>Polvijärvi</span><label class="switch"><input type="checkbox" value="polvijärvi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Rääkkylä</span><label class="switch"><input type="checkbox" value="rääkkylä" /><span class="slider"></span></label></div>
<div class="option-row"><span>Tohmajärvi</span><label class="switch"><input type="checkbox" value="tohmajärvi" /><span class="slider"></span></label></div>
<div class="option-row region-header"><span>Kainuu</span><label class="switch"><input type="checkbox" value="kainuu" /><span class="slider"></span></label></div>
<div class="option-row"><span>Hyrynsalmi</span><label class="switch"><input type="checkbox" value="hyrynsalmi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kajaani</span><label class="switch"><input type="checkbox" value="kajaani" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kuhmo</span><label class="switch"><input type="checkbox" value="kuhmo" /><span class="slider"></span></label></div>
<div class="option-row"><span>Paltamo</span><label class="switch"><input type="checkbox" value="paltamo" /><span class="slider"></span></label></div>
<div class="option-row"><span>Puolanka</span><label class="switch"><input type="checkbox" value="puolanka" /><span class="slider"></span></label></div>
<div class="option-row"><span>Ristijärvi</span><label class="switch"><input type="checkbox" value="ristijärvi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Sotkamo</span><label class="switch"><input type="checkbox" value="sotkamo" /><span class="slider"></span></label></div>
<div class="option-row"><span>Suomussalmi</span><label class="switch"><input type="checkbox" value="suomussalmi" /><span class="slider"></span></label></div>
<div class="option-row region-header"><span>South Savo</span><label class="switch"><input type="checkbox" value="south savo" /><span class="slider"></span></label></div>
<div class="option-row"><span>Enonkoski</span><label class="switch"><input type="checkbox" value="enonkoski" /><span class="slider"></span></label></div>
<div class="option-row"><span>Hirvensalmi</span><label class="switch"><input type="checkbox" value="hirvensalmi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Juva</span><label class="switch"><input type="checkbox" value="juva" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kangasniemi</span><label class="switch"><input type="checkbox" value="kangasniemi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Mikkeli</span><label class="switch"><input type="checkbox" value="mikkeli" /><span class="slider"></span></label></div>
<div class="option-row"><span>Mäntyharju</span><label class="switch"><input type="checkbox" value="mäntyharju" /><span class="slider"></span></label></div>
<div class="option-row"><span>Pieksämäki</span><label class="switch"><input type="checkbox" value="pieksämäki" /><span class="slider"></span></label></div>
<div class="option-row"><span>Puumala</span><label class="switch"><input type="checkbox" value="puumala" /><span class="slider"></span></label></div>
<div class="option-row"><span>Rantasalmi</span><label class="switch"><input type="checkbox" value="rantasalmi" /><span class="slider"></span></label></div>
<div class="option-row"><span>Savonlinna</span><label class="switch"><input type="checkbox" value="savonlinna" /><span class="slider"></span></label></div>
<div class="option-row"><span>Sulkava</span><label class="switch"><input type="checkbox" value="sulkava" /><span class="slider"></span></label></div>
<div class="option-row region-header"><span>Åland</span><label class="switch"><input type="checkbox" value="åland" /><span class="slider"></span></label></div>
<div class="option-row"><span>Brändö</span><label class="switch"><input type="checkbox" value="brändö" /><span class="slider"></span></label></div>
<div class="option-row"><span>Eckerö</span><label class="switch"><input type="checkbox" value="eckerö" /><span class="slider"></span></label></div>
<div class="option-row"><span>Finström</span><label class="switch"><input type="checkbox" value="finström" /><span class="slider"></span></label></div>
<div class="option-row"><span>Föglö</span><label class="switch"><input type="checkbox" value="föglö" /><span class="slider"></span></label></div>
<div class="option-row"><span>Geta</span><label class="switch"><input type="checkbox" value="geta" /><span class="slider"></span></label></div>
<div class="option-row"><span>Hammarland</span><label class="switch"><input type="checkbox" value="hammarland" /><span class="slider"></span></label></div>
<div class="option-row"><span>Jomala</span><label class="switch"><input type="checkbox" value="jomala" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kumlinge</span><label class="switch"><input type="checkbox" value="kumlinge" /><span class="slider"></span></label></div>
<div class="option-row"><span>Kökar</span><label class="switch"><input type="checkbox" value="kökar" /><span class="slider"></span></label></div>
<div class="option-row"><span>Lemland</span><label class="switch"><input type="checkbox" value="lemland" /><span class="slider"></span></label></div>
<div class="option-row"><span>Lumparland</span><label class="switch"><input type="checkbox" value="lumparland" /><span class="slider"></span></label></div>
<div class="option-row"><span>Maarianhamina</span><label class="switch"><input type="checkbox" value="maarianhamina" /><span class="slider"></span></label></div>
<div class="option-row"><span>Saltvik</span><label class="switch"><input type="checkbox" value="saltvik" /><span class="slider"></span></label></div>
<div class="option-row"><span>Sottunga</span><label class="switch"><input type="checkbox" value="sottunga" /><span class="slider"></span></label></div>
<div class="option-row"><span>Sund</span><label class="switch"><input type="checkbox" value="sund" /><span class="slider"></span></label></div>
<div class="option-row"><span>Vårdö</span><label class="switch"><input type="checkbox" value="vårdö" /><span class="slider"></span></label></div>
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


