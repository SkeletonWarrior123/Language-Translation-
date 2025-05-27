// Background service worker for the extension
chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.sync.set({ translationEnabled: false });
});

chrome.action.onClicked.addListener((tab) => {
  chrome.storage.sync.get(['translationEnabled'], (result) => {
    const newState = !result.translationEnabled;
    chrome.storage.sync.set({ translationEnabled: newState });
    
    // Update the icon to reflect the state
    const iconPath = newState ? 'extension/icons/icon16.png' : 'extension/icons/icon48.png';
    chrome.action.setIcon({ path: iconPath });
    
    // Send message to content script
    chrome.tabs.sendMessage(tab.id, {
      action: 'TOGGLE_TRANSLATION',
      enabled: newState
    });
  });
});