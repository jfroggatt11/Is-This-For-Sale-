document.querySelector('#open').addEventListener('click', () => {
  chrome.tabs.create({url: chrome.runtime.getURL('runner.html')});
  window.close();
});
