document.addEventListener('DOMContentLoaded', function () {
    var currentTime = new Date();

    // Define class start and end times for each class
    var classTimes = [
        
            { id: 'class-10-english', startHour: 19, endHour: 19 },
            { id: 'class-10-math', startHour: 0, endHour: 0},
            { id: 'class-10-science', startHour: 20, endHour: 20 },
            { id: 'class-10-optional-math', startHour: 20, endHour: 20 },
            { id: 'class-10-economics', startHour: 0, endHour: 0 },

            { id: 'class-10-math-dristhi', startHour: 0, endHour: 0 },
            { id: 'class-10-science-dristhi', startHour: 0, endHour: 0 },
            { id: 'class-10-optional-math-dristhi', startHour: 0, endHour: 0 },
            { id: 'class-10-economics-dristhi', startHour: 0, endHour: 0 },
            { id: 'class-10-english-dristhi', startHour: 0, endHour: 0 },

            { id: 'class-11-english', startHour: 7, endHour: 7 },
            { id: 'class-11-physics', startHour: 12, endHour: 12 },
            { id: 'class-11-chemistry', startHour: 12, endHour: 12 },
            { id: 'class-11-math', startHour: 12, endHour: 12 },
            { id: 'class-11-biology', startHour: 12, endHour: 12 },
            { id: 'class-11-account', startHour: 12, endHour: 12 },
            { id: 'class-11-economics', startHour: 12, endHour: 12 },
            { id: 'class-12-physics', startHour: 12, endHour: 12 },
            { id: 'class-12-chemistry', startHour: 12, endHour: 12 },
            { id: 'class-12-math', startHour: 20, endHour: 20 },
            { id: 'class-12-biology', startHour: 12, endHour: 12 },
            { id: 'class-12-account', startHour: 18, endHour: 19},
            { id: 'class-12-economics', startHour: 19, endHour: 20 },
            { id: 'class-12-social', startHour: 20, endHour: 20 },
            { id: 'class-12-english', startHour: 21, endHour: 22 },
            { id: 'ctevt-first-year-physics-m', startHour: 12, endHour: 12 },
            { id: 'ctevt-first-year-chemistry-m', startHour: 21, endHour: 21 },
            { id: 'ctevt-first-year-math-m', startHour: 21, endHour: 21 },
            { id: 'ctevt-first-year-zoology-m', startHour: 12, endHour: 12 },
            { id: 'ctevt-first-year-botany-m', startHour: 12, endHour: 12 }
            
        


        // Add more classes as needed with their respective startHour and endHour
    ];

    // Iterate over each class
    classTimes.forEach(function (classTime) {
        var article = document.getElementById(classTime.id);
        if (article) {
            // Check if current time is between class start and end times
            if (currentTime.getHours() >= classTime.startHour && currentTime.getHours() < classTime.endHour) {
                // Show blinking image and join class button
                article.querySelector('.blimg').style.display = 'block';
                article.querySelector('.button.jncl').style.display = 'inline-flex';
            }
        }
    });
});
