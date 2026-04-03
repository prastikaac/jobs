// GTranslate Settings
window.gtranslateSettings = window.gtranslateSettings || {};
window.gtranslateSettings["43217984"] = {
    default_language: "en",
    languages: [
        "fi", "sv", "en", "ru", "et", "uk", "hi", "ne", "ur", "ar", "so", "ku", "fa", "zh-CN",
        "sq", "vi", "tr", "th", "bn", "tl", "ps", "ta", "pa", "ro", "pl", "iw", "es", "fr", "de"
    ],
    wrapper_selector: "#gt-mordadam-43217984",
    native_language_names: 1,
    flag_style: "2d",
    flag_size: 24,
    horizontal_position: "inline",
    flags_location: "https://findjobsinfinland.fi/images/flags/"
};

// Dropdown Toggle Logic
document.addEventListener('click', function (event) {
    const toggleButton = document.querySelector('.gt_switcher-popup');
    const dropdown = document.querySelector('.gt_white_content');

    if (!toggleButton || !dropdown) return;

    const isClickInsideButton = toggleButton.contains(event.target);
    const isClickInsideDropdown = dropdown.contains(event.target);

    if (!isClickInsideButton && !isClickInsideDropdown) {
        dropdown.style.display = 'none';
        toggleButton.classList.remove('active');
    } else if (isClickInsideButton) {
        const isActive = toggleButton.classList.contains('active');
        dropdown.style.display = isActive ? 'none' : 'block';
        toggleButton.classList.toggle('active');
    }
});
