// Function to display notifications
function displayNotifications(notifications) {
    var notificationCount = document.getElementById('notification-count');
    var notificationsContainer = document.getElementById('notifications-container');
    var notificationsOuterDiv = document.getElementById('notifications-outer-div');

    // Retrieve read notifications from cache
    var readNotifications = JSON.parse(localStorage.getItem('readNotifications')) || [];

    // Clear previous notifications
    notificationsContainer.innerHTML = '';

    // Add close button to notifications container
    var closeContainerButton = document.createElement('span');
    closeContainerButton.classList.add('close-container-button');
    closeContainerButton.innerHTML = '&times;';
    closeContainerButton.addEventListener('click', function() {
        notificationsContainer.style.display = 'none';
        notificationsOuterDiv.style.display = 'none'; // Hide blur background
        adjustZIndex(); // Adjust z-index when closing
    });
    notificationsContainer.appendChild(closeContainerButton);

    // Generate notifications
    var unreadCount = 0;
    var isNewNotificationDisplayed = false;
    notifications.forEach(function(notification, index) {
        var notificationElement = document.createElement('div');
        notificationElement.classList.add('notification');
        if (readNotifications.includes(notification.title)) {
            notificationElement.classList.add('read');
        } else {
            notificationElement.classList.add('unread');
            unreadCount++;
            if (!isNewNotificationDisplayed) {
                var newNotificationText = document.createElement('div');
                newNotificationText.classList.add('new-notification');
                newNotificationText.textContent = 'New Notification';
                notificationsContainer.appendChild(newNotificationText);
                isNewNotificationDisplayed = true;
            }
        }
        var previewText = truncate(notification.content, 20);
        notificationElement.innerHTML = `
            <span class="unread-dot"></span>
            <div class="notification-title">${notification.title}</div>
            <div class="notification-preview">${previewText}...</div>
            <div class="notification-content" style="display:none;">${notification.content}</div>
            <span class="close-button" style="display:none;">&times;</span>
        `;
        notificationsContainer.appendChild(notificationElement);
    });

    // Update notification count
    if (unreadCount > 0) {
        notificationCount.innerText = unreadCount;
        notificationCount.style.display = 'inline';
    } else {
        notificationCount.style.display = 'none';
    }

    // Show notifications container
    notificationsContainer.style.display = 'none';

    // Event listener for clicking on notifications
    notificationsContainer.addEventListener('click', function(event) {
        var notification = event.target.closest('.notification');
        if (notification) {
            notification.classList.toggle('expanded');
            var closeButton = notification.querySelector('.close-button');
            if (notification.classList.contains('expanded')) {
                closeButton.style.display = 'inline';
                notification.querySelector('.notification-preview').style.display = 'none';
                notification.querySelector('.notification-content').style.display = 'block';
                notificationsOuterDiv.style.display = 'block'; // Show blur background
            } else {
                notification.querySelector('.notification-preview').style.display = 'block';
                notification.querySelector('.notification-content').style.display = 'none';
                closeButton.style.display = 'none';
                notificationsOuterDiv.style.display = 'none'; // Hide blur background
            }
            if (notification.classList.contains('unread')) {
                notification.classList.remove('unread');
                notification.classList.add('read');
                var notificationTitle = notification.querySelector('.notification-title').textContent;
                // Store read notification in cache
                readNotifications.push(notificationTitle);
                localStorage.setItem('readNotifications', JSON.stringify(readNotifications));
                // Update notification count
                unreadCount--;
                if (unreadCount > 0) {
                    notificationCount.innerText = unreadCount;
                } else {
                    notificationCount.style.display = 'none';
                }
            }

            // Close the expanded notification when the close button is clicked
            closeButton.addEventListener('click', function(event) {
                event.stopPropagation(); // Prevent triggering the notification's click event
                notification.classList.remove('expanded');
                notification.querySelector('.notification-preview').style.display = 'block';
                notification.querySelector('.notification-content').style.display = 'none';
                closeButton.style.display = 'none';
            });
        }
    });

    // Event listener for clicking outside the notifications container
    document.addEventListener('click', function(event) {
        if (!notificationsContainer.contains(event.target) && !document.getElementById('notification-icon').contains(event.target)) {
            notificationsContainer.style.display = 'none';
            notificationsOuterDiv.style.display = 'none'; // Hide blur background
            adjustZIndex(); // Adjust z-index when closing
        }
    });
}

// Toggle visibility of notifications container
function toggleNotifications() {
    var notificationContainer = document.getElementById("notifications-container");
    var notificationsOuterDiv = document.getElementById('notifications-outer-div');
    var isVisible = notificationContainer.style.display === "block";
    notificationContainer.style.display = isVisible ? "none" : "block";
    notificationsOuterDiv.style.display = isVisible ? "none" : "block"; // Toggle blur background
    adjustZIndex(); // Adjust z-index when toggling visibility
}

// Function to adjust the z-index of the notification icon
function adjustZIndex() {
    var notificationIcon = document.getElementById('notification-icon');
    var notificationContainer = document.getElementById('notifications-container');
    var isVisible = notificationContainer.style.display === "block";
    notificationIcon.style.zIndex = isVisible ? '9999' : '1';
}

// Event listener for clicking on notification icon
document.getElementById("notification-icon").addEventListener("click", toggleNotifications);

// Function to truncate text
function truncate(str, numWords) {
    var words = str.split(' ');
    if (words.length > numWords) {
        return words.slice(0, numWords).join(' ');
    } else {
        return str;
    }
}

// Initially display notifications after 1 second
displayNotifications([



    { title: "Class 10 Classes Start from 25th of Aashad ", content: "Get ready to kickstart your learning journey in Aashad! 📚 Class starts soon in Noteswift, so don't miss out! Hurry up and enroll now to secure your spot and make the most of this academic opportunity. Let's make Aashad a month filled with knowledge, growth, and success! 🎓 <br> <br> #EnrollNow #Class10Aashad #Noteswift <br> " },

    { title: "Public Holiday on May 1!", content: "Please be informed that there will be a public holiday on May 1st, observed as 'Majdur Diwas' (Labour Day). <br> <br>  As a result, there will be no classes held on that day. <br> <br> Enjoy your extended weekend!" },

    { title: "Service will Down for a month!", content: "Please be informed that the Service will be undergoing maintenance and will be temporarily unavailable throughout the Baishak month. This downtime is necessary as we are in the process of developing an updated version of the app to enhance your user experience. <br> <br> We anticipate that the upgraded app will be up and running smoothly starting from the Jestha month. We apologize for any inconvenience this may cause and appreciate your patience and understanding during this period." }
]);
