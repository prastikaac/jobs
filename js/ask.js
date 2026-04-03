
// Function to create a profile card
function createProfileCard(name, imageUrl, linkUrl) {
    // Create the profile card div
    var profileCardContainer = document.getElementById('profile-card-container');
    var profileCard = document.createElement('div');
    profileCard.className = 'profile-card';

    // Create the profile picture
    var profilePicture = document.createElement('img');
    profilePicture.className = 'profile-picture';
    profilePicture.src = imageUrl;
    profilePicture.alt = 'Profile Picture';

    // Create the profile info div
    var profileInfo = document.createElement('div');
    profileInfo.className = 'profile-info';

    // Create the profile name
    var profileName = document.createElement('div');
    profileName.className = 'profile-name';
    profileName.textContent = name;

    // Create the ask button
    var askButton = document.createElement('a');
    askButton.className = 'ask-button';
    askButton.href = linkUrl;
    askButton.textContent = 'Ask now!';

    // Append elements to their respective parents
    profileInfo.appendChild(profileName);
    profileInfo.appendChild(askButton);
    profileCard.appendChild(profilePicture);
    profileCard.appendChild(profileInfo);
    profileCardContainer.appendChild(profileCard);
}

// Create multiple profile cards
createProfileCard("NoteSwift AI ChatBot", 'https://findjobsinfinland.fi/images/ai.png', 'https://findjobsinfinland.fi/ai');
createProfileCard("NEB Class 10 Group", 'https://findjobsinfinland.fi/images/class-10-png.png', 'http://chat.whatsapp.com/CXIMt0enPDf1W1aCEkijYB');
createProfileCard("NEB Class 11 Group", 'https://findjobsinfinland.fi/images/class-11-png.png', 'http://chat.whatsapp.com/BXVAxLYFXhY80Z36rcXJH6');
createProfileCard("NEB Class 12 Group", 'https://findjobsinfinland.fi/images/class-12-png.png', 'http://chat.whatsapp.com/BXVAxLYFXhY80Z36rcXJH6');

// Add more profile cards as needed
