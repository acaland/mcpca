/* Progressive enhancement only: tabs and the mobile menu. The page is complete without it. */
(function () {
  'use strict';

  // Mobile nav
  var toggle = document.querySelector('.nav-toggle');
  var nav = document.getElementById('site-nav');
  if (toggle && nav) {
    toggle.addEventListener('click', function () {
      var open = nav.classList.toggle('is-open');
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    nav.addEventListener('click', function (e) {
      if (e.target.closest('a')) {
        nav.classList.remove('is-open');
        toggle.setAttribute('aria-expanded', 'false');
      }
    });
  }

  // Tabs (WAI-ARIA pattern, manual activation with arrow keys)
  document.querySelectorAll('[data-tabs]').forEach(function (root) {
    var tabs = Array.prototype.slice.call(root.querySelectorAll('[role="tab"]'));
    var panels = Array.prototype.slice.call(root.querySelectorAll('[role="tabpanel"]'));

    function activate(tab, focus) {
      tabs.forEach(function (t) {
        var selected = t === tab;
        t.setAttribute('aria-selected', selected ? 'true' : 'false');
        t.tabIndex = selected ? 0 : -1;
      });
      panels.forEach(function (p) {
        p.hidden = p.id !== tab.getAttribute('aria-controls');
      });
      if (focus) tab.focus();
    }

    tabs.forEach(function (tab, i) {
      tab.addEventListener('click', function () { activate(tab, false); });
      tab.addEventListener('keydown', function (e) {
        var next;
        if (e.key === 'ArrowRight') next = tabs[(i + 1) % tabs.length];
        else if (e.key === 'ArrowLeft') next = tabs[(i - 1 + tabs.length) % tabs.length];
        else if (e.key === 'Home') next = tabs[0];
        else if (e.key === 'End') next = tabs[tabs.length - 1];
        if (next) { e.preventDefault(); activate(next, true); }
      });
    });

    // Deep link: #casi-studenti selects that tab
    var m = location.hash.match(/^#casi-(\w+)$/);
    if (m) {
      var target = root.querySelector('#tab-' + m[1]);
      if (target) activate(target, false);
    }
  });

  // Rotating word in the hero title (Teams -> Copilot -> ChatGPT -> Claude)
  document.querySelectorAll('.rotate').forEach(function (el) {
    var words;
    try { words = JSON.parse(el.getAttribute('data-words')); } catch (e) { return; }
    if (!words || words.length < 2) return;
    // Reserve the width of the longest word so the heading does not reflow.
    var probe = document.createElement('span');
    probe.style.cssText = 'position:absolute;visibility:hidden;white-space:nowrap;font:inherit';
    el.parentNode.appendChild(probe);
    var max = 0;
    words.forEach(function (w) { probe.textContent = w; max = Math.max(max, probe.getBoundingClientRect().width); });
    probe.remove();
    if (max) el.style.minWidth = Math.ceil(max) + 'px';
    var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var i = 0;
    setInterval(function () {
      i = (i + 1) % words.length;
      if (reduce) { el.textContent = words[i]; return; }
      el.classList.add('is-out');
      setTimeout(function () { el.textContent = words[i]; el.classList.remove('is-out'); }, 350);
    }, 2600);
  });
})();
