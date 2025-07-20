
  const ulElement = document.querySelector('ul.mnMn[itemscope][itemtype="https://schema.org/SiteNavigationElement"]');
if (ulElement) {
  const htmlToInsert = `
    <li class="hm popli">
      <div id="pp-card-wrapper" class="">
        <div class="pp-card" id="pp-card">
          <div class="close-btn dispc" id="pp-card-closebtn">✖</div>
          <div class="pp-image-wrapper">
            <img src="/images/user.png" alt="Profile" class="pp-image" id="profileImage" />
            <div class="camera-icon" id="cameraIcon">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
                <path d="M149.1 64.8L138.7 96 64 96C28.7 96 0 124.7 0 160L0 416c0 35.3 28.7 64 64 64l384 0c35.3 0 64-28.7 64-64l0-256c0-35.3-28.7-64-64-64l-74.7 0L362.9 64.8C356.4 45.2 338.1 32 317.4 32L194.6 32c-20.7 0-39 13.2-45.5 32.8zM256 192a96 96 0 1 1 0 192 96 96 0 1 1 0-192z" />
              </svg>
            </div>
            <input type="file" id="imageUploadInput" accept="image/*" style="display: none;" />
          </div>
          <div class="pp-details">
            <div class="pp-field" id="userName">
              <svg xmlns="http://www.w3.org/2000/svg" fill="currentColor" class="bi bi-person" viewBox="0 0 16 16">
                <path d="M8 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6m2-3a2 2 0 1 1-4 0 2 2 0 0 1 4 0m4 8c0 1-1 1-1 1H3s-1 0-1-1 1-4 6-4 6 3 6 4m-1-.004c-.001-.246-.154-.986-.832-1.664C11.516 10.68 10.289 10 8 10s-3.516.68-4.168 1.332c-.678.678-.83 1.418-.832 1.664z" />
              </svg>
              <span id="nameText">Loading...</span>
            </div>
            <div class="pp-field" id="userEmail">
              <svg xmlns="http://www.w3.org/2000/svg" fill="currentColor" class="bi bi-envelope" viewBox="0 0 16 16">
                <path d="M0 4a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2V4zm13.5-.5H2.5a.5.5 0 0 0-.5.5v.217l6 3.6 6-3.6V4a.5.5 0 0 0-.5-.5zm.5 2.383-5.857 3.514a.5.5 0 0 1-.286.083.5.5 0 0 1-.286-.083L1 5.883V12a.5.5 0 0 0 .5.5h12a.5.5 0 0 0 .5-.5V5.883z" />
              </svg>
              <span id="emailText">Loading...</span>
            </div>
            <div class="pp-field" id="userPhone">
              <svg xmlns="http://www.w3.org/2000/svg" fill="currentColor" class="bi bi-telephone" viewBox="0 0 16 16">
                <path d="M3.654 1.328a.678.678 0 0 0-1.015-.063L1.605 2.3c-.483.484-.661 1.169-.45 1.77a17.6 17.6 0 0 0 4.168 6.608 17.6 17.6 0 0 0 6.608 4.168c.601.211 1.286.033 1.77-.45l1.034-1.034a.678.678 0 0 0-.063-1.015l-2.307-1.794a.68.68 0 0 0-.58-.122l-2.19.547a1.75 1.75 0 0 1-1.657-.459L5.482 8.062a1.75 1.75 0 0 1-.46-1.657l.548-2.19a.68.68 0 0 0-.122-.58z" />
              </svg>
              <span id="phoneText">Loading...</span>
            </div>
          </div>
        </div>
      </div>
    </li>
    <li class="br dissign dismob"></li>
    <li class="hm dissign dispc" id="pcuserdetails">
      <a class="a" itemprop="url">
        <svg style="width: 20px; height: 20px;" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512">
          <path d="M224 256A128 128 0 1 0 224 0a128 128 0 1 0 0 256zm-45.7 48C79.8 304 0 383.8 0 482.3C0 498.7 13.3 512 29.7 512l388.6 0c16.4 0 29.7-13.3 29.7-29.7C448 383.8 368.2 304 269.7 304l-91.4 0z" />
        </svg>
        <span class="n" itemprop="name">View User Information</span>
      </a>
    </li>
    <li class="br dissign dispc"></li>
    <li class="hm dissign" id="edit-pp-information">
      <a class="a" href="https://findjobsinfinland.fi/edit-profile" itemprop="url">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 512">
          <path d="M224 256A128 128 0 1 0 224 0a128 128 0 1 0 0 256zm-45.7 48C79.8 304 0 383.8 0 482.3C0 498.7 13.3 512 29.7 512l293.1 0c-3.1-8.8-3.7-18.4-1.4-27.8l15-60.1c2.8-11.3 8.6-21.5 16.8-29.7l40.3-40.3c-32.1-31-75.7-50.1-123.9-50.1l-91.4 0zm435.5-68.3c-15.6-15.6-40.9-15.6-56.6 0l-29.4 29.4 71 71 29.4-29.4c15.6-15.6 15.6-40.9 0-56.6l-14.4-14.4zM375.9 417c-4.1 4.1-7 9.2-8.4 14.9l-15 60.1c-1.4 5.5 .2 11.2 4.2 15.2s9.7 5.6 15.2 4.2l60.1-15c5.6-1.4 10.8-4.3 14.9-8.4L576.1 358.7l-71-71L375.9 417z" />
        </svg>
        <span class="n" itemprop="name">Edit Profile Information</span>
      </a>
    </li>
    <li class="hm dissign" id="signout-btn">
      <a id="logoffbtn" class="a" itemprop="url">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
          <path d="M377.9 105.9L500.7 228.7c7.2 7.2 11.3 17.1 11.3 27.3s-4.1 20.1-11.3 27.3L377.9 406.1c-6.4 6.4-15 9.9-24 9.9c-18.7 0-33.9-15.2-33.9-33.9l0-62.1-128 0c-17.7 0-32-14.3-32-32l0-64c0-17.7 14.3-32 32-32l128 0 0-62.1c0-18.7 15.2-33.9 33.9-33.9c9 0 17.6 3.6 24 9.9zM160 96L96 96c-17.7 0-32 14.3-32 32l0 256c0 17.7 14.3 32 32 32l64 0c17.7 0 32 14.3 32 32s-14.3 32-32 32l-64 0c-53 0-96-43-96-96L0 128C0 75 43 32 96 32l64 0c17.7 0 32 14.3 32 32s-14.3 32-32 32z" />
        </svg>
        <span class="n" itemprop="name">Sign Out</span>
      </a>
    </li>
      <li class="br dissign">
                  </li>
  `;
  ulElement.insertAdjacentHTML('afterbegin', htmlToInsert);
}
