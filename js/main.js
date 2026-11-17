/* ============================================
   main.js — theme toggle
   The pre-paint script in each page's <head> applies a stored choice,
   or dark on phones. Only a click is stored.
   ============================================ */

(function () {
  var root = document.documentElement,
      btn = document.querySelector('.theme-toggle'),
      os = window.matchMedia('(prefers-color-scheme: dark)'),
      colors = { light: '#fbfcfc', dark: '#0d2a31' };

  try { localStorage.removeItem('theme'); } catch (e) {} // legacy key

  function current() { return root.getAttribute('data-theme') || (os.matches ? 'dark' : 'light'); }

  function paint() {
    var dark = current() === 'dark', set = root.getAttribute('data-theme');
    if (btn) {
      btn.textContent = dark ? '☀' : '☽';
      btn.setAttribute('aria-label', dark ? 'Switch to light mode' : 'Switch to dark mode');
    }
    document.querySelectorAll('meta[name="theme-color"]').forEach(function (m) {
      m.content = colors[set || ((m.media || '').indexOf('dark') > -1 ? 'dark' : 'light')];
    });
  }

  if (btn) btn.addEventListener('click', function () {
    var next = current() === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    try { localStorage.setItem('theme-choice', next); } catch (e) {}
    paint();
  });

  if (os.addEventListener) os.addEventListener('change', function () { if (!root.hasAttribute('data-theme')) paint(); });
  paint();
})();
