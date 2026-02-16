/* ============================================
   main.js — Dark mode + Quote filtering
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

  // ---- Mobile Menu ----
  const menuToggle = document.querySelector('.menu-toggle');
  const mobileNav = document.getElementById('mobile-nav');
  if (menuToggle && mobileNav) {
    menuToggle.addEventListener('click', () => {
      const open = mobileNav.hidden;
      mobileNav.hidden = !open;
      menuToggle.setAttribute('aria-expanded', open);
      menuToggle.textContent = open ? 'Close' : 'Menu';
    });

    mobileNav.querySelectorAll('a').forEach((link) => {
      link.addEventListener('click', () => {
        mobileNav.hidden = true;
        menuToggle.setAttribute('aria-expanded', 'false');
        menuToggle.textContent = 'Menu';
      });
    });
  }

  // ---- Quote Tag Filtering ----
  const tagContainer = document.querySelector('.quote-tags');
  if (tagContainer) {
    const buttons = tagContainer.querySelectorAll('button');
    const quotes = document.querySelectorAll('.quote-list li');

    buttons.forEach((btn) => {
      btn.addEventListener('click', () => {
        const tag = btn.dataset.tag;

        // Toggle active state
        if (btn.classList.contains('active')) {
          btn.classList.remove('active');
          quotes.forEach((q) => (q.style.display = ''));
          return;
        }

        buttons.forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');

        quotes.forEach((q) => {
          const tags = q.dataset.tags ? q.dataset.tags.split(',') : [];
          q.style.display = tags.includes(tag) ? '' : 'none';
        });
      });
    });
  }
})();
