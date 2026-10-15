(() => {
  document.querySelectorAll('[data-project-carousel]').forEach(track => {
    const controls = track.closest('.research-section').querySelector('.project-controls');
    if (!controls) return;
    const previous = controls.querySelector('[data-project-step="-1"]');
    const next = controls.querySelector('[data-project-step="1"]');
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

    function updateControls() {
      const end = Math.max(0, track.scrollWidth - track.clientWidth);
      previous.disabled = track.scrollLeft <= 1;
      next.disabled = track.scrollLeft >= end - 1;
    }

    controls.querySelectorAll('button').forEach(button => {
      button.addEventListener('click', () => {
        const card = track.querySelector('.project-card');
        if (!card) return;
        const gap = parseFloat(window.getComputedStyle(track).columnGap) || 0;
        track.scrollBy({
          left: Number(button.dataset.projectStep) * (card.getBoundingClientRect().width + gap),
          behavior: reducedMotion.matches ? 'auto' : 'smooth'
        });
      });
    });

    track.addEventListener('scroll', updateControls, { passive: true });
    window.addEventListener('resize', updateControls);
    if ('ResizeObserver' in window) new ResizeObserver(updateControls).observe(track);
    controls.hidden = false;
    updateControls();
  });
})();
