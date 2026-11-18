/* Mobile navigation.
 * Only runs the menu logic when a toggle and a menu exist on the page.
 */
(function () {
  'use strict';

  var toggle = document.querySelector('[aria-controls="mobile-menu"]');
  var menu = document.getElementById('mobile-menu');
  if (!toggle || !menu) {
    return;
  }

  function close() {
    toggle.setAttribute('aria-expanded', 'false');
    menu.hidden = true;
    document.body.classList.remove('menu-open');
  }

  function open() {
    toggle.setAttribute('aria-expanded', 'true');
    menu.hidden = false;
    document.body.classList.add('menu-open');
  }

  toggle.addEventListener('click', function () {
    var expanded = toggle.getAttribute('aria-expanded') === 'true';
    if (expanded) {
      close();
    } else {
      open();
    }
  });

  menu.addEventListener('click', function (event) {
    if (event.target.closest('a')) {
      close();
    }
  });

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') {
      close();
    }
  });

  window.addEventListener('resize', function () {
    if (window.innerWidth > 820) {
      close();
    }
  });
})();
