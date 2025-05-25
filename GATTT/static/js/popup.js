document.addEventListener('DOMContentLoaded', function() {
  const dataEl = document.getElementById("popup-data");
  if (!dataEl) return;
  
  try {
    const popupData = JSON.parse(dataEl.textContent || '[]');
    
    popupData.forEach(([category, message]) => {
      if (category === 'popup') {
        const popup = document.getElementById("popupModal");
        const messageBox = document.getElementById("popupMessage");
        
        if (popup && messageBox) {
          messageBox.textContent = message;
          popup.style.display = "block";

          popup.addEventListener('click', function(event) {
            if (event.target === popup) {
              popup.style.display = "none";
            }
          });
        }
      }
    });
  } catch (e) {
    console.error("Popup error:", e);
  }
});