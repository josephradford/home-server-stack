const KioskApp = (() => {
  const IDLE_TIMEOUT_MS = 30 * 1000;       // return to screensaver after 30s of no touch on idle/nav
  const PANEL_TIMEOUT_MS = 5 * 60 * 1000;  // panels get their own longer timeout
  const PHOTO_INTERVAL_MS = 60 * 1000;
  const POLL_INTERVAL_MS = 30 * 1000;
  const WAKE_GRACE_MS = 5 * 60 * 1000;      // grace period after a manual touch-wake before the schedule can re-sleep it

  let idleTimer = null;
  let currentView = 'idle';
  let currentStation = null;
  let sleepWindow = { sleep_start: '23:00', sleep_end: '07:00' };
  let isSleeping = false;
  let wokeAt = 0;

  function $(id) { return document.getElementById(id); }

  function showView(id) {
    document.querySelectorAll('.view').forEach(el => el.classList.add('hidden'));
    $('view-nav').classList.add('hidden');  // nav is an overlay on top of idle, not part of the .view group - see showNav()
    $(id).classList.remove('hidden');
  }

  function stopRadio() {
    const audio = $('radio-audio');
    if (!audio || audio.paused) return;
    audio.pause();
    currentStation = null;
    nowPlayingStationName = null;
    nowPlayingTrackMeta = '';
    document.querySelectorAll('#radio-list li.playing').forEach(el => el.classList.remove('playing'));
    updateNowPlayingDisplay();
  }

  function showIdle() {
    currentView = 'idle';
    showView('view-idle');
    resetIdleTimer();
  }

  function showNav() {
    currentView = 'nav';
    // Not showView() - nav sits on top of the idle photo (dimmed via CSS)
    // rather than replacing it, so the screensaver stays visible underneath.
    $('view-nav').classList.remove('hidden');
    resetIdleTimer();
  }

  function showPanel(name) {
    currentView = 'panel';
    showView(`view-${name}`);
    if (name === 'radio') loadRadioPanel();
    if (name === 'calendar') loadCalendarPanel();
    if (name === 'recipes') loadRecipesPanel();
    resetIdleTimer();
  }

  function resetIdleTimer() {
    if (idleTimer) clearTimeout(idleTimer);
    // Idle timer only runs on the idle/nav views - an open panel gets its own
    // longer timeout instead, so a recipe never gets interrupted mid-read.
    const timeout = currentView === 'panel' ? PANEL_TIMEOUT_MS : IDLE_TIMEOUT_MS;
    idleTimer = setTimeout(showIdle, timeout);
  }

  function formatEventWhen(e) {
    const start = new Date(e.start);
    const now = new Date();
    const isSameDay = start.toDateString() === now.toDateString();
    const tomorrow = new Date(now);
    tomorrow.setDate(now.getDate() + 1);
    const isTomorrow = start.toDateString() === tomorrow.toDateString();

    const dayLabel = isSameDay ? 'Today'
      : isTomorrow ? 'Tomorrow'
      : start.toLocaleDateString([], {weekday: 'short', month: 'short', day: 'numeric'});

    if (e.all_day) return dayLabel;

    // hour12: false -> 24-hour clock throughout the kiosk.
    const time = start.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit', hour12: false});
    return `${dayLabel}, ${time}`;
  }

  async function refreshOverlay() {
    try {
      const [weather, calendar] = await Promise.all([
        fetch('/api/weather').then(r => r.json()),
        fetch('/api/calendar/events?limit=2').then(r => r.json()),
      ]);
      if (weather.observations) {
        const location = weather.location ? weather.location.name : '';
        const today = weather.forecast_daily && weather.forecast_daily[0];
        const condition = today ? today.short_text : '';
        const tempLine = [
          `${weather.observations.temp}°C`,
          today && today.temp_max != null ? `(max ${today.temp_max}°C)` : null,
          location ? `· ${location}` : null,
        ].filter(Boolean).join(' ');
        $('overlay-weather').innerHTML = [tempLine, condition].filter(Boolean).join('<br>');
      } else {
        $('overlay-weather').textContent = 'Weather unavailable';
      }
      $('overlay-events').innerHTML = calendar.events
        .map(e => `${e.title} — ${formatEventWhen(e)}`)
        .join('<br>');
    } catch (e) {
      console.error('overlay refresh failed', e);
    }
  }

  async function refreshPhoto() {
    try {
      const photo = await fetch('/api/photos/random').then(r => r.json());
      $('idle-photo').src = photo.image_url;
      // Explicitly labelled ("📷") and distinct from the clock ("🕐") so
      // it's unambiguous which timestamp is "now" and which is "when this
      // photo was taken" - they can be very different.
      const meta = [photo.taken_at ? new Date(photo.taken_at).toLocaleDateString() : null, photo.place]
        .filter(Boolean).join(' · ');
      $('overlay-photo-meta-value').textContent = meta || 'Unknown date';
    } catch (e) {
      console.error('photo refresh failed', e);
    }
  }

  function updateClock() {
    const now = new Date();
    $('overlay-time-value').textContent = now.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit', hour12: false});
    $('overlay-date').textContent = now.toLocaleDateString([], {weekday: 'long', month: 'long', day: 'numeric'});
  }

  let nowPlayingStationName = null;
  let nowPlayingTrackMeta = '';  // best-effort ID3 metadata, see attachMetadataListener()

  function updateNowPlayingDisplay() {
    const el = $('overlay-nowplaying');
    if (!nowPlayingStationName) {
      el.classList.add('hidden');
      el.textContent = '';
      return;
    }
    el.textContent = ['📻 ' + nowPlayingStationName, nowPlayingTrackMeta].filter(Boolean).join(' — ');
    el.classList.remove('hidden');
  }

  function attachMetadataListener(audio) {
    // Best-effort: Safari exposes ID3 metadata embedded in some HLS audio
    // streams as WebVTT-like text track cues. Not every station's stream
    // carries this, and support varies - if nothing shows up, the "now
    // playing" line just falls back to the station name alone (set by the
    // caller before this runs). Wrapped defensively since this touches a
    // less-common browser API surface that's hard to verify without a real
    // device + live stream in front of you.
    try {
      if (!audio.textTracks) return;
      audio.textTracks.addEventListener('addtrack', (addEvent) => {
        const track = addEvent.track;
        track.mode = 'hidden';
        track.addEventListener('cuechange', () => {
          const cue = track.activeCues && track.activeCues[0];
          if (!cue) return;
          // ID3 cues typically expose a parsed frame on .value (e.g. a
          // TIT2/title frame's text) or fall back to .text.
          const text = (cue.value && (cue.value.text || cue.value.data)) || cue.text || '';
          nowPlayingTrackMeta = String(text).trim();
          updateNowPlayingDisplay();
        });
      });
    } catch (e) {
      console.error('ID3 metadata listener unsupported', e);
    }
  }

  async function loadRadioPanel() {
    const list = $('radio-list');
    if (list.dataset.loaded) return;
    const { stations } = await fetch('/api/radio/stations').then(r => r.json());
    list.innerHTML = stations.map(s =>
      `<li data-url="${s.stream_url}" data-id="${s.id}" data-name="${s.name}">${s.name}</li>`
    ).join('');
    list.dataset.loaded = 'true';

    const audio = $('radio-audio');
    attachMetadataListener(audio);

    list.addEventListener('click', (e) => {
      const li = e.target.closest('li');
      if (!li) return;
      resetIdleTimer();
      if (currentStation === li.dataset.id) {
        stopRadio();
      } else {
        list.querySelectorAll('li').forEach(el => el.classList.remove('playing'));
        audio.src = li.dataset.url;
        audio.play().catch(err => console.error('playback failed', err));
        currentStation = li.dataset.id;
        nowPlayingStationName = li.dataset.name;
        nowPlayingTrackMeta = '';
        li.classList.add('playing');
        updateNowPlayingDisplay();
      }
    });
  }

  async function loadCalendarPanel() {
    const list = $('calendar-list');
    const { events } = await fetch('/api/calendar/events?limit=20').then(r => r.json());
    list.innerHTML = events.map(e => {
      const start = new Date(e.start);
      const when = e.all_day
        ? start.toLocaleDateString([], {weekday: 'short', month: 'short', day: 'numeric'})
        : start.toLocaleString([], {weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false});
      return `<li><strong>${e.title}</strong><br>${when}</li>`;
    }).join('') || '<li>No upcoming events</li>';
  }

  async function loadRecipesPanel() {
    $('recipes-detail-view').classList.add('hidden');
    $('recipes-list-view').classList.remove('hidden');

    const list = $('recipes-list');
    const { recipes } = await fetch('/api/recipes').then(r => r.json());
    list.innerHTML = recipes.map(r => `<li data-id="${r.id}">${r.title}</li>`).join('');

    list.onclick = async (e) => {
      const li = e.target.closest('li');
      if (!li) return;
      resetIdleTimer();
      const recipe = await fetch(`/api/recipes/${li.dataset.id}`).then(r => r.json());
      $('recipe-title').textContent = recipe.title;
      $('recipe-ingredients').innerHTML = recipe.ingredients.map(i => `<li>${i}</li>`).join('');
      $('recipe-steps').innerHTML = recipe.steps.map(s => `<li>${s}</li>`).join('');
      $('recipes-list-view').classList.add('hidden');
      $('recipes-detail-view').classList.remove('hidden');
    };
  }

  function parseTimeToMinutes(hhmm) {
    const [h, m] = hhmm.split(':').map(Number);
    return h * 60 + m;
  }

  function isWithinSleepWindow(now) {
    const nowMinutes = now.getHours() * 60 + now.getMinutes();
    const start = parseTimeToMinutes(sleepWindow.sleep_start);
    const end = parseTimeToMinutes(sleepWindow.sleep_end);
    // overnight windows wrap past midnight (e.g. 23:00 -> 07:00)
    return start > end
      ? (nowMinutes >= start || nowMinutes < end)
      : (nowMinutes >= start && nowMinutes < end);
  }

  function enterSleep() {
    if (isSleeping) return;
    isSleeping = true;
    if (idleTimer) clearTimeout(idleTimer);
    stopRadio();
    showView('view-sleep');
  }

  function wake() {
    isSleeping = false;
    wokeAt = Date.now();
    showIdle();
  }

  async function checkSleepSchedule() {
    let anyoneHome = true;
    try {
      const presence = await fetch('/api/presence').then(r => r.json());
      anyoneHome = presence.anyone_home;
    } catch (e) {
      console.error('presence check failed, assuming home', e);
    }

    const withinWakeGrace = Date.now() - wokeAt < WAKE_GRACE_MS;

    if ((isWithinSleepWindow(new Date()) || !anyoneHome) && !withinWakeGrace) {
      enterSleep();
    } else if (isSleeping) {
      wake();
    }
  }

  function init() {
    // Bound to both touchstart (real touchscreen) and click (mouse, and
    // browsers' synthetic click after a touch) so the idle screen reveals
    // navigation whichever input the device sends. Idempotent either way -
    // a touchstart's showNav()/wake() followed by the synthetic click is a
    // harmless no-op repeat, not a double transition.
    function handleIdleActivation() {
      if (isSleeping) { wake(); return; }   // touch always wakes instantly, regardless of schedule
      if (currentView === 'idle') { showNav(); return; }
      resetIdleTimer();
    }
    document.addEventListener('touchstart', handleIdleActivation);
    document.addEventListener('click', handleIdleActivation);

    document.querySelectorAll('#view-nav button').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        showPanel(btn.dataset.panel);
      });
    });

    // Clicking the dimmed backdrop itself (anywhere that isn't one of the
    // three buttons) returns straight to idle, rather than waiting out the
    // idle timeout.
    $('view-nav').addEventListener('click', (e) => {
      if (e.target.closest('button')) return;  // button's own listener (above) handles this
      e.stopPropagation();
      showIdle();
    });

    $('recipes-back-to-list').addEventListener('click', () => {
      resetIdleTimer();
      $('recipes-detail-view').classList.add('hidden');
      $('recipes-list-view').classList.remove('hidden');
    });

    fetch('/api/config').then(r => r.json()).then(cfg => { sleepWindow = cfg; });

    updateClock();
    setInterval(updateClock, 1000);
    refreshOverlay();
    setInterval(refreshOverlay, POLL_INTERVAL_MS);
    refreshPhoto();
    setInterval(refreshPhoto, PHOTO_INTERVAL_MS);
    checkSleepSchedule();
    setInterval(checkSleepSchedule, 60 * 1000);

    showIdle();
  }

  document.addEventListener('DOMContentLoaded', init);

  return { showIdle, showPanel, resetIdleTimer };
})();
