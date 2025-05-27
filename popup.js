document.addEventListener('DOMContentLoaded', function() {
  const toggle = document.getElementById('toggleTranslation');
  const toggleLabel = document.getElementById('toggleLabel');
  const statusMessage = document.getElementById('statusMessage');
  const settingsBtn = document.getElementById('settingsBtn');

  // Load the current state
  chrome.storage.sync.get(['translationEnabled'], function(result) {
    toggle.checked = result.translationEnabled || false;
    updateLabel();
  });

  // Toggle translation
  toggle.addEventListener('change', function() {
    chrome.storage.sync.set({ translationEnabled: this.checked }, function() {
      updateLabel();
      
      // Send message to current tab
      chrome.tabs.query({ active: true, currentWindow: true }, function(tabs) {
        chrome.tabs.sendMessage(tabs[0].id, {
          action: 'TOGGLE_TRANSLATION',
          enabled: this.checked
        });
      }.bind(this));
    }.bind(this));
  });

  function updateLabel() {
    if (toggle.checked) {
      toggleLabel.textContent = 'Disable Translation';
      statusMessage.textContent = 'Translating page to Hindi...';
    } else {
      toggleLabel.textContent = 'Enable Translation';
      statusMessage.textContent = 'Translation is disabled';
    }
  }

  settingsBtn.addEventListener('click', function() {
    // Open options page if you add one
    chrome.runtime.openOptionsPage();
  });
});