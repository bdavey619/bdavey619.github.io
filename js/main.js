/* ============================================
   main.js — Dark mode + scroll entrance
   ============================================ */

(function () {
  // ---- Dark Mode ----
  const toggle = document.querySelector('.theme-toggle');
  if (toggle) {
    const setTheme = (theme) => {
      document.documentElement.setAttribute('data-theme', theme);
      localStorage.setItem('theme', theme);
      toggle.textContent = theme === 'dark' ? '☀' : '☽';
      toggle.setAttribute('aria-label', theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode');
    };

    // Init: check localStorage, then system preference
    const saved = localStorage.getItem('theme');
    if (saved) {
      setTheme(saved);
    } else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
      setTheme('dark');
    } else {
      setTheme('light');
    }

    toggle.addEventListener('click', () => {
      const current = document.documentElement.getAttribute('data-theme');
      setTheme(current === 'dark' ? 'light' : 'dark');
    });
  }

  // ---- Scroll entrance ----
  const reveals = document.querySelectorAll('[data-reveal]');
  if (reveals.length) {
    const noMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (noMotion || !('IntersectionObserver' in window)) {
      reveals.forEach((el) => el.classList.add('in'));
    } else {
      const io = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('in');
            io.unobserve(entry.target);
          }
        });
      }, { rootMargin: '0px 0px -8% 0px', threshold: 0.05 });
      reveals.forEach((el) => io.observe(el));
    }
  }

})();
