'use strict';
document.querySelector('#status').textContent = 'This companion is retired. The CLI now launches fresh, isolated Chromium automatically.';
document.querySelector('#connect').addEventListener('submit', event => event.preventDefault());
for (const input of document.querySelectorAll('input, button')) input.disabled = true;
