/* Theme switcher.
 * The inline head script sets the initial theme before paint to avoid a flash.
 * This module handles the toggle button and system-preference changes.
 */
(function () {
  'use strict';

  var STORAGE_KEY = 'survey.theme';
  var root = document.documentElement;
  var media = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;

  function getStored() {
    try {
      return localStorage.getItem(STORAGE_KEY) || 'system';
    } catch (error) {
      return 'system';
    }
  }

  function resolve(mode) {
    if (mode === 'light' || mode === 'dark') {
      return mode;
    }
    return media && media.matches ? 'dark' : 'light';
  }

  function apply(mode) {
    root.setAttribute('data-theme', resolve(mode));
  }

  function setMode(mode) {
    try {
      localStorage.setItem(STORAGE_KEY, mode);
    } catch (error) {
      /* Storage may be unavailable; the theme still applies for this page. */
    }
    apply(mode);
  }

  function toggle() {
    var current = root.getAttribute('data-theme') || 'light';
    setMode(current === 'dark' ? 'light' : 'dark');
  }

  document.addEventListener('click', function (event) {
    var trigger = event.target.closest('[data-theme-toggle]');
    if (trigger) {
      event.preventDefault();
      toggle();
    }
  });

  if (media && typeof media.addEventListener === 'function') {
    media.addEventListener('change', function () {
      if (getStored() === 'system') {
        apply('system');
      }
    });
  }

  apply(getStored());
})();
