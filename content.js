let translationEnabled = false;

// Listen for messages from the background script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'TOGGLE_TRANSLATION') {
    translationEnabled = request.enabled;
    if (translationEnabled) {
      startTranslation();
    } else {
      removeTranslations();
    }
  }
});

// Function to translate page content
async function startTranslation() {
  // Get all text nodes in the document
  const walker = document.createTreeWalker(
    document.body,
    NodeFilter.SHOW_TEXT,
    null,
    false
  );

  const textNodes = [];
  let node;
  while (node = walker.nextNode()) {
    if (node.nodeValue.trim() && !isInsideScriptOrStyle(node)) {
      textNodes.push(node);
    }
  }

  // Process nodes in chunks to avoid overwhelming the API
  for (let i = 0; i < textNodes.length; i += 5) {
    const chunk = textNodes.slice(i, i + 5);
    await processNodes(chunk);
  }
}

function isInsideScriptOrStyle(node) {
  return node.parentNode.tagName === 'SCRIPT' || node.parentNode.tagName === 'STYLE';
}

async function processNodes(nodes) {
  const texts = nodes.map(node => node.nodeValue.trim()).filter(text => text.length > 0);
  
  if (texts.length === 0) return;

  try {
    const translations = await translateTexts(texts);
    
    nodes.forEach((node, index) => {
      if (translations[index]) {
        const span = document.createElement('span');
        span.className = 'hindi-translation';
        span.dataset.original = node.nodeValue;
        span.textContent = translations[index];
        node.parentNode.replaceChild(span, node);
      }
    });
  } catch (error) {
    console.error('Translation error:', error);
  }
}

async function translateTexts(texts) {
  try {
    const response = await fetch('http://localhost:5000/translate', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ text: texts.join('\n---SEPARATOR---\n') }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return data.translatedText.split('\n---SEPARATOR---\n');
  } catch (error) {
    console.error('Translation failed:', error);
    return texts; // Return original texts if translation fails
  }
}

function removeTranslations() {
  const translatedElements = document.querySelectorAll('.hindi-translation');
  translatedElements.forEach(el => {
    const textNode = document.createTextNode(el.dataset.original);
    el.parentNode.replaceChild(textNode, el);
  });
}