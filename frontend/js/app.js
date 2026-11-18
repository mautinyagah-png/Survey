/* Page-level initialisation.
 * Kept intentionally small; feature logic lives in dedicated modules.
 */
(function () {
  'use strict';

  var yearEl = document.querySelector('[data-current-year]');
  if (yearEl) {
    yearEl.textContent = String(new Date().getFullYear());
  }
})();
