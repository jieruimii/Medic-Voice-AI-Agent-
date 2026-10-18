// Keep the recording canvas at 1920 × 1080; smaller previews scale uniformly.
function fitScene() {
  document.documentElement.style.setProperty('--scale', Math.min(innerWidth / 1920, innerHeight / 1080));
}
fitScene();
addEventListener('resize', fitScene);
