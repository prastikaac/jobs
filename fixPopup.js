const fs = require("fs");
let t = fs.readFileSync("js/popupLogic.js", "utf8");
t = t.split("document.getElementById(\"jobAlertPopup\").style.display").join("if(document.getElementById(\"jobAlertPopup\")) document.getElementById(\"jobAlertPopup\").style.display");
fs.writeFileSync("js/popupLogic.js", t);
