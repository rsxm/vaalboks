"use strict";

const phrase = document.getElementById("room-phrase");
const feedback = document.getElementById("phrase-feedback");

phrase.addEventListener("input", () => {
  const words = phrase.value.trim().split(/\s+/).filter(Boolean);
  const length = phrase.value.trim().length;
  if (words.length >= 6 || length >= 30) {
    feedback.textContent = "Good for a persistent room on a trusted LAN.";
    feedback.className = "access-help strength-good";
  } else if (words.length >= 4 || length >= 18) {
    feedback.textContent = "Reasonable for a short-lived trusted-LAN session.";
    feedback.className = "access-help strength-medium";
  } else {
    feedback.textContent =
      "Easy to guess. Use more words for anything persistent.";
    feedback.className = "access-help strength-weak";
  }
});
