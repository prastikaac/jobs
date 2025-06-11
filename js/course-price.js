document.addEventListener('DOMContentLoaded', function () {
  const prices = {
    "class-10-english": "Rs. 1199",
    "class-10-math": "Rs. 1199",
    "class-10-economics": "Rs. 1199",
    "class-10-opt-math": "Rs. 1199",
    "class-10-science": "Rs. 1199",
    "class-11-english": "Rs. 1399",
    "class-11-physics": "Rs. 1399",
    "class-11-chemistry": "Rs. 1399",
    "class-11-math": "Rs. 1399",
    "class-11-account": "Rs. 1399",
    "class-11-economics": "Rs. 1399",
    "class-11-biology": "Rs. 1399",
    "class-12-english": "Rs. 1399",
    "class-12-physics": "Rs. 1399",
    "class-12-chemistry": "Rs. 1399",
    "class-12-math": "Rs. 1399",
    "class-12-account": "Rs. 1399",
    "class-12-economics": "Rs. 1399",
    "class-12-biology": "Rs. 1399",
    "ctevt-combo-medical": "Rs. 1999",
    "class-12-social": "Rs. 1399",
    "class-12-management-combo": "Rs. 2999",
    "class-10-combo-dristhi": "Rs. 999"
  };

  for (let className in prices) {
    if (prices.hasOwnProperty(className)) {
      let element = document.querySelector('.' + className);
      if (element) {
        element.setAttribute('data-text', prices[className]);
      } else {
        console.log('Element with class ' + className + ' not found.');
      }
    }
  }
});
