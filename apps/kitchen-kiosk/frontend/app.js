const KioskApp = (() => {
  const IDLE_TIMEOUT_MS = 30 * 1000;       // return to screensaver after 30s of no touch on idle/nav
  const PANEL_TIMEOUT_MS = 5 * 60 * 1000;  // panels get their own longer timeout
  const PHOTO_INTERVAL_MS = 60 * 1000;
  const POLL_INTERVAL_MS = 30 * 1000;

  let idleTimer = null;
  let currentView = 'idle';

  function $(id) { return document.getElementById(id); }

  function showView(id) {
    document.querySelectorAll('.view').forEach(el => el.classList.add('hidden'));
    $(id).classList.remove('hidden');
  }

  function showIdle() {
    currentView = 'idle';
    showView('view-idle');
    resetIdleTimer();
  }

  function showNav() {
    currentView = 'nav';
    showView('view-nav');
    resetIdleTimer();
  }

  function showPanel(name) {
    currentView = 'panel';
    showView(`view-${name}`);
    resetIdleTimer();
  }

  function resetIdleTimer() {
    if (idleTimer) clearTimeout(idleTimer);
    // Idle timer only runs on the idle/nav views - an open panel gets its own
    // longer timeout instead, so a recipe never gets interrupted mid-read.
    const timeout = currentView === 'panel' ? PANEL_TIMEOUT_MS : IDLE_TIMEOUT_MS;
    idleTimer = setTimeout(showIdle, timeout);
  }

  async function refreshOverlay() {
    try {
      const [weather, calendar] = await Promise.all([
        fetch('/api/weather').then(r => r.json()),
        fetch('/api/calendar/events?limit=2').then(r => r.json()),
      ]);
      $('overlay-weather').textContent = weather.current
        ? `${weather.current.temp}°C` : 'Weather unavailable';
      $('overlay-events').innerHTML = calendar.events
        .map(e => `${e.title} — ${new Date(e.start).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})}`)
        .join('<br>');
    } catch (e) {
      console.error('overlay refresh failed', e);
    }
  }

  async function refreshPhoto() {
    try {
      const photo = await fetch('/api/photos/random').then(r => r.json());
      $('idle-photo').src = photo.image_url;
      const meta = [photo.taken_at ? new Date(photo.taken_at).toLocaleDateString() : null, photo.place]
        .filter(Boolean).join(' · ');
      $('overlay-photo-meta').textContent = meta;
    } catch (e) {
      console.error('photo refresh failed', e);
    }
  }

  function updateClock() {
    const now = new Date();
    $('overlay-time').textContent = now.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
    $('overlay-date').textContent = now.toLocaleDateString([], {weekday: 'long', month: 'long', day: 'numeric'});
  }

  function init() {
    document.addEventListener('touchstart', () => {
      if (currentView === 'idle') { showNav(); return; }
      resetIdleTimer();
    });

    document.querySelectorAll('#view-nav button').forEach(btn => {
      btn.addEventListener('click', () => showPanel(btn.dataset.panel));
    });

    updateClock();
    setInterval(updateClock, 1000);
    refreshOverlay();
    setInterval(refreshOverlay, POLL_INTERVAL_MS);
    refreshPhoto();
    setInterval(refreshPhoto, PHOTO_INTERVAL_MS);

    showIdle();
  }

  document.addEventListener('DOMContentLoaded', init);

  return { showIdle, showPanel, resetIdleTimer };
})();
