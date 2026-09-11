(() => {
  'use strict';
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const finePointer = matchMedia('(hover: hover) and (pointer: fine)');
  const sky = document.createElement('div');
  sky.className = 'aurora-sky';
  sky.setAttribute('aria-hidden', 'true');
  for (let i = 0; i < 3; i++) {
    const orb = document.createElement('i');
    orb.className = 'aurora-orb';
    sky.append(orb);
  }
  document.body.prepend(sky);
  document.querySelectorAll('.brand img').forEach(logo => {
    const ring = document.createElement('span');
    ring.className = 'logo-ring';
    logo.before(ring);
    ring.append(logo);
  });
  document.addEventListener('click', event => {
    const button = event.target.closest('.btn');
    if (!button || button.disabled || reduced.matches) return;
    button.querySelectorAll('.button-ripple').forEach(ripple => ripple.remove());
    const rect = button.getBoundingClientRect();
    const diameter = Math.hypot(rect.width, rect.height) * 2;
    const ripple = document.createElement('span');
    ripple.className = 'button-ripple';
    ripple.setAttribute('aria-hidden', 'true');
    ripple.style.width = ripple.style.height = `${diameter}px`;
    ripple.style.left = `${(event.detail ? event.clientX - rect.left : rect.width / 2) - diameter / 2}px`;
    ripple.style.top = `${(event.detail ? event.clientY - rect.top : rect.height / 2) - diameter / 2}px`;
    button.append(ripple);
    setTimeout(() => ripple.remove(), 850);
  });
  const visual = document.querySelector('.visual');
  let frame = 0;
  if (visual) {
    visual.addEventListener('pointermove', event => {
      if (reduced.matches || !finePointer.matches) return;
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const rect = visual.getBoundingClientRect();
        const x = Math.max(-1, Math.min(1, (event.clientX - rect.left) / rect.width * 2 - 1));
        const y = Math.max(-1, Math.min(1, (event.clientY - rect.top) / rect.height * 2 - 1));
        visual.style.setProperty('--tilt-x', `${-y * 4}deg`);
        visual.style.setProperty('--tilt-y', `${x * 5}deg`);
      });
    }, { passive: true });
    const reset = () => {
      cancelAnimationFrame(frame);
      visual.style.removeProperty('--tilt-x');
      visual.style.removeProperty('--tilt-y');
    };
    visual.addEventListener('pointerleave', reset);
    reduced.addEventListener('change', reset);
    finePointer.addEventListener('change', reset);
  }
  const tone = value => /validé|terminé|payée|réglée/i.test(value) ? 'success' : /refusé|annulé/i.test(value) ? 'danger' : /attente|impayée/i.test(value) ? 'warning' : 'info';
  function badges(root) {
    root.querySelectorAll('.status').forEach(cell => {
      if (cell.querySelector('.status-badge')) return;
      const badge = document.createElement('span');
      badge.className = 'status-badge';
      badge.dataset.tone = tone(cell.textContent);
      badge.textContent = cell.textContent;
      cell.replaceChildren(badge);
    });
    root.querySelectorAll('.price').forEach(price => {
      if (price.textContent.trim() !== 'Bientôt disponible' || price.querySelector('.coming-soon-badge')) return;
      const badge = document.createElement('span');
      badge.className = 'coming-soon-badge';
      badge.textContent = price.textContent;
      price.replaceChildren(badge);
    });
  }
  badges(document);
  const observer = new MutationObserver(() => badges(document));
  document.querySelectorAll('#staffDash,#clientDash,#serviceCards,#trainingCards').forEach(root => observer.observe(root, { childList: true, subtree: true }));
  const header = document.querySelector('.top');
  const scroll = () => header?.classList.toggle('scrolled', scrollY > 12);
  addEventListener('scroll', scroll, { passive: true });
  scroll();
})();
