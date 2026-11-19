// Plays EVENTS (injected by build.mjs: [{ k, arg, body }]) into the terminal markup of page.html.
(() => {
  const $ = (id) => document.getElementById(id);
  const log = $('log'), scroller = $('scroll'), typed = $('typed');
  const spinEl = $('spin'), glyphEl = $('glyph'), verbEl = $('verb'), metaEl = $('meta');
  const term = document.querySelector('.term');
  const prevBtn = $('prev'), nextBtn = $('next'), startBtn = $('start'), endBtn = $('end');
  const playBtn = $('play'), playLabel = $('playLabel'), playIcon = $('playIcon'), progressEl = $('progress');

  const EV = EVENTS;
  const isPrompt = (e) => e.k === 'user' || e.k === 'slash';
  const TURNS = EV.filter(isPrompt).length;
  // Steps are what Previous/Next move by: [events before the first prompt], then per turn the user's
  // prompt, typed but not sent, and the agent's reply, which starts by sending it (no reply step
  // when a prompt has none).
  const STEPS = [[]];
  for (const e of EV) {
    const last = STEPS[STEPS.length - 1];
    if (isPrompt(e) || (last.length && isPrompt(last[0]))) STEPS.push([e]);
    else last.push(e);
  }

  // ---- playback state ----
  let run = 0, speed, paused = false, instant = false, autoscroll = true, turn = 0;
  let pos = 0; // steps completed: 0 start-up screen, 1 turn 0 (Claude Code open), 2 first prompt typed, ...
  // CSS animations divide their durations by --speed, so they keep pace with wait()
  const setSpeed = (s) => { speed = s; term.style.setProperty('--speed', s); };
  setSpeed(2);
  // `continuous` off holds playback after every turn, `holdNext` after the current step only.
  // `skipStep` fast-forwards the current step, `seek` the first N steps (used to go back).
  // `release` is set while playback is held and continues it when called. `ended`: the last step is done.
  let continuous = true, holdNext = false, ended = false, skipStep = false, seek = -1, release = null;
  let unsent = null; // the prompt typed in the input box and not sent yet
  const fast = () => instant || skipStep || pos < seek;
  class Abort {}
  async function wait(ms, id) {
    let left = ms;
    while (left > 0) {
      if (id !== run) throw new Abort();
      if (fast()) return;
      await new Promise((r) => setTimeout(r, 16));
      if (!paused) left -= 16 * speed;
    }
    if (id !== run) throw new Abort();
  }

  const stick = () => { if (autoscroll) scroller.scrollTop = scroller.scrollHeight; };
  scroller.addEventListener('scroll', () => {
    autoscroll = scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < 40;
  });

  const div = (cls) => { const d = document.createElement('div'); if (cls) d.className = cls; return d; };
  const span = (cls, text) => { const s = document.createElement('span'); if (cls) s.className = cls; if (text != null) s.textContent = text; return s; };
  function row(mark, mcls, cls) {
    const r = div('row ' + (cls || ''));
    const g = span('g ' + (mcls || ''), mark);
    const c = div('c');
    r.append(g, c);
    log.appendChild(r);
    stick();
    return c;
  }

  // inline markup: `code` and **bold**
  function segs(s) {
    const out = [], re = /(`[^`]+`|\*\*[^*]+\*\*)/g;
    let i = 0, m;
    while ((m = re.exec(s))) {
      if (m.index > i) out.push(['', s.slice(i, m.index)]);
      const t = m[0];
      out.push(t[0] === '`' ? ['code', t.slice(1, -1)] : ['b', t.slice(2, -2)]);
      i = m.index + t.length;
    }
    if (i < s.length) out.push(['', s.slice(i)]);
    return out;
  }
  async function stream(el, s, cps, id) {
    const step = Math.max(1, Math.round((cps * 16) / 1000));
    for (const [c, t] of segs(s)) {
      const sp = span(c, '');
      el.appendChild(sp);
      let i = 0;
      while (i < t.length) {
        if (fast()) { sp.textContent = t; break; }
        i = Math.min(t.length, i + step);
        sp.textContent = t.slice(0, i);
        stick();
        await wait(16, id);
      }
    }
    stick();
  }

  // ---- spinner ----
  const GLYPHS = ['·', '✢', '✳', '✶', '✻', '✽', '✻', '✶', '✳', '✢'];
  let spinTimer = null, spinFrame = 0, spinMs = 0, spinCap = 0;
  function spinStart(verb, cap) {
    spinCap = cap; spinMs = 0; spinFrame = 0;
    verbEl.textContent = verb + '…';
    metaEl.textContent = '(0s · esc to interrupt)';
    spinEl.hidden = false;
    clearInterval(spinTimer);
    spinTimer = setInterval(() => {
      if (paused) return;
      spinFrame++; spinMs += 100 * speed;
      glyphEl.textContent = GLYPHS[spinFrame % GLYPHS.length];
      metaEl.textContent = `(${Math.min(spinCap, Math.floor(spinMs / 450))}s · esc to interrupt)`;
    }, 100);
    stick();
  }
  function spinStop() { clearInterval(spinTimer); spinEl.hidden = true; }
  // Spin until the turn's @done. Verb and duration come from its text ("Baked for 9s" -> "Baking", 9).
  function spinFor(e, verb) {
    const rest = [];
    for (let i = EV.indexOf(e) + 1; i < EV.length && !isPrompt(EV[i]); i++) rest.push(EV[i]);
    if (!rest.length) return false;
    const done = rest.find((x) => x.k === 'done');
    const v = done && done.arg.match(/^(\S+?)ed\b/);
    const t = done && done.arg.match(/(?:(\d+)m\s*)?(\d+)s/);
    spinStart(verb || (v ? v[1] + 'ing' : 'Thinking'), t ? (+t[1] || 0) * 60 + +t[2] : 99);
    return true;
  }

  // ---- event handlers ----
  const H = {
    async banner(e, id) {
      const b = div('banner');
      e.body.forEach((line, i) => {
        const m = line.match(/^([\s▀-▟]*[▀-▟])(.*)$/); // leading block-character logo
        if (m) b.appendChild(span('logo', m[1]));
        const rest = span('dim', null);
        for (const [c, t] of segs(m ? m[2] : line)) rest.appendChild(span(c, t));
        b.appendChild(rest);
        if (i < e.body.length - 1) b.appendChild(document.createTextNode('\n'));
      });
      log.appendChild(b);
      if (fast()) return;
      b.classList.add('draw'); // drawn left to right
      await wait(1600, id);
    },
    async note(e, id) { await wait(500, id); row('⏺', 'm-dim', 'note').textContent = e.arg; stick(); },
    async dim(e, id) { await wait(600, id); row('', '', 'dimrow').textContent = '  ' + e.arg; stick(); },
    async user(e, id) {
      await wait(900, id);
      spinStop();
      turn++; progressEl.textContent = `turn ${turn}/${TURNS}`;
      typed.textContent = '';
      for (const ch of e.arg) {
        if (fast()) break;
        typed.textContent += ch;
        await wait(26 + Math.random() * 46, id);
      }
      typed.textContent = e.arg;
      unsent = e; // the step ends with the prompt typed; send() runs when the next step begins
    },
    async slash(e, id) { return H.user(e, id); },
    async spin(e) { spinFor(e, e.arg); },
    async 'tool!'(e, id) { return H.tool(e, id, true); },
    async tool(e, id, err = false) {
      await wait(500, id);
      const c = row('⏺', 'm-run', 'tool');
      const g = c.previousSibling;
      const m = e.arg.match(/^([^(]+)\(([\s\S]*)\)$/);
      c.append(span('b', m ? m[1] : e.arg), document.createTextNode(m ? `(${m[2]})` : ''));
      stick();
      await wait(1300, id);
      g.className = 'g ' + (err ? 'm-err' : 'm-ok');
      const o = div('out');
      c.appendChild(o);
      for (let i = 0; i < e.body.length; i++) {
        o.append(span('', i === 0 ? '⎿' : ''), span(i === 0 && err ? 'err' : /^\s*\d+ \+/.test(e.body[i]) ? 'add' : /^\s*\d+ -/.test(e.body[i]) ? 'del' : '', e.body[i]));
        stick();
        await wait(45, id);
      }
    },
    async say(e, id) {
      await wait(700, id);
      const c = row('⏺', '', 'say');
      let pre = null, fence = false;
      for (const line of e.body) {
        if (line === '```') { fence = !fence; pre = null; continue; } // fenced block: shown verbatim
        if (fence || /^[┌│├└]/.test(line)) { // box-drawing table or fenced block: shown verbatim
          if (!pre) { const w = div('tblwrap'); pre = document.createElement('pre'); w.appendChild(pre); c.appendChild(w); }
          pre.textContent += (pre.textContent ? '\n' : '') + line;
          stick();
          await wait(60, id);
          continue;
        }
        pre = null;
        if (!line.trim()) { c.appendChild(div('gap')); continue; }
        let cls = 'p', text = line, mark = '', m;
        if ((m = line.match(/^## (.*)/))) { cls = 'h'; text = m[1]; }
        else if ((m = line.match(/^\s+- (.*)/))) { cls = 'li li2'; mark = '-'; text = m[1]; }
        else if ((m = line.match(/^- (.*)/))) { cls = 'li'; mark = '-'; text = m[1]; }
        else if ((m = line.match(/^(\d+\.) (.*)/))) { cls = 'li num'; mark = m[1]; text = m[2]; }
        const d = div(cls);
        if (mark) d.appendChild(span('bm', mark));
        const t = span('', null);
        d.appendChild(t);
        c.appendChild(d);
        await stream(t, text, 320, id);
      }
    },
    // AskUserQuestion. e.body is [[question, answer], ...]. A card asks them one by one and marks the
    // chosen answer, then folds into the line Claude Code prints. Fast-forward shows that line only.
    async ask(e, id) {
      if (!fast()) {
        await wait(600, id);
        const spun = !spinEl.hidden;
        spinEl.hidden = true;
        const card = div('ask'), head = div('ask-head');
        const pips = e.body.map(() => document.createElement('i'));
        head.appendChild(span('ask-tag', e.body.length > 1 ? 'Questions' : 'Question'));
        if (pips.length > 1) { const p = span('ask-pips', null); p.append(...pips); head.appendChild(p); }
        card.appendChild(head);
        log.appendChild(card);
        let body = null;
        for (let i = 0; i < e.body.length && !fast(); i++) {
          const [question, answer] = e.body[i];
          if (body) body.remove();
          body = div('ask-body');
          const q = div('ask-q'), a = div('ask-a');
          body.appendChild(q);
          card.appendChild(body);
          pips[i].className = 'on';
          stick();
          await wait(500, id);
          await stream(q, question, 90, id);
          await wait(700, id);
          a.append(span('ask-cur', '❯'), span('', answer), span('ask-ok', '✔'));
          body.appendChild(a);
          stick();
          await wait(1200, id);
          a.classList.add('picked');
          pips[i].className = 'ok';
          await wait(1400, id);
        }
        card.classList.add('out');
        await wait(500, id);
        card.remove();
        spinEl.hidden = !spun;
      }
      const c = row('⏺', '', 'asked');
      c.textContent = "User answered Claude's questions:";
      const o = div('out');
      e.body.forEach(([question, answer], i) => o.append(span('', i === 0 ? '⎿' : ''), span('', `· ${question} → ${answer}`)));
      c.appendChild(o);
      stick();
    },
    async done(e, id) {
      await wait(500, id);
      spinStop();
      row('✻', 'm-dim', 'done').textContent = e.arg;
      stick();
      await wait(600, id);
    },
  };

  // Sends the typed prompt: it moves from the input box into the transcript and the spinner starts.
  async function send(id) {
    const e = unsent;
    unsent = null;
    await wait(450, id);
    typed.textContent = '';
    autoscroll = true;
    row('❯', '', 'user').textContent = e.arg;
    stick();
    if (spinFor(e)) await wait(700, id);
    if (e.k !== 'slash' || !e.body.length) return;
    await wait(400, id);
    const o = div('out');
    o.append(span('', '⎿'), span('', e.body.join(' ')));
    row('', '', 'dimrow').appendChild(o);
    stick();
  }

  // ---- runner & controls ----
  const PLAY_ICON = 'M8 5v14l11-7z', PAUSE_ICON = 'M8 5v14M16 5v14';
  // Middle button: Pause while a turn plays, Play when paused or held between turns, Replay at the end.
  function sync() {
    const playing = !ended && !paused && !release;
    playLabel.textContent = ended ? 'Replay' : playing ? 'Pause' : 'Play';
    playIcon.setAttribute('d', playing ? PAUSE_ICON : PLAY_ICON);
    // Greyed out when there is nowhere to go: Next/End after the last step, Previous/Start at turn 0 or before.
    nextBtn.disabled = endBtn.disabled = ended;
    prevBtn.disabled = startBtn.disabled = pos < 2 && (ended || !!release);
    playBtn.classList.toggle('cue', !!release && pos < 2); // waiting for the viewer to begin
  }
  function setPaused(p) { paused = p; sync(); }
  // Holds playback until Play or Next (or Previous, Start, End) releases it.
  function hold(id) {
    return new Promise((res, rej) => {
      release = () => { release = null; sync(); if (id === run) res(); else rej(new Abort()); };
      sync();
    });
  }
  // Previous (dir -1) and Next (dir 1). Step still animating: finish it at once and hold there.
  // Step finished: Next plays the following step with its animation and holds after it;
  // Previous shows the preceding step, complete, and stays held until Play.
  function nav(dir) {
    if (!release && !ended) { skipStep = holdNext = true; setPaused(false); return; }
    if (dir > 0) { if (release) { holdNext = true; release(); } return; }
    if (pos > 1) play(pos - 1);
  }
  // Start-up screen: a small amber CRT powers on and `claude` is typed at its shell prompt.
  // Skipped when fast-forwarding; the shell line stays.
  async function boot(id) {
    const line = div('shell'), cmd = span('', '');
    line.append(span('ps', '$ '), cmd, span('caret', null));
    log.appendChild(line);
    if (!fast()) {
      void term.offsetWidth; // restart the power-on animation on a replay
      term.classList.add('crt', 'power');
      await wait(2400, id);
      for (const ch of 'claude') {
        if (fast()) break;
        cmd.textContent += ch;
        await wait(170 + Math.random() * 140, id);
      }
    }
    cmd.textContent = 'claude';
  }
  // Enter is pressed: the CRT grows into the Claude Code window (CSS transitions on leaving `.crt`).
  async function open(id) {
    log.querySelector('.shell .caret').remove();
    term.classList.remove('crt', 'power');
    await wait(1400, id);
  }
  // Plays from the top. With `start`, that many steps appear at once (1: turn 0), then playback holds.
  async function play(start = -1) {
    const id = ++run;
    if (release) release();
    log.innerHTML = ''; typed.textContent = ''; spinStop();
    term.classList.remove('crt', 'power');
    pos = turn = 0; progressEl.textContent = `turn 0/${TURNS}`;
    autoscroll = true; instant = matchMedia('(prefers-reduced-motion: reduce)').matches;
    skipStep = holdNext = ended = false; seek = start; unsent = null;
    setPaused(false);
    try {
      await boot(id);
      for (let s = 0; s < STEPS.length; s++) {
        pos = s;
        skipStep = false;
        // Hold on the start-up screen and at turn 0 always, like title slides. Later: after
        // Previous/Next, or between turns when continuous play is off.
        const stop = s === seek || (!fast() && (s < 2 || holdNext || (!continuous && isPrompt(STEPS[s][0]))));
        holdNext = false;
        if (s === seek) seek = -1;
        if (stop) await hold(id);
        if (s === 0) await open(id);
        if (unsent) await send(id);
        for (const e of STEPS[s]) await H[e.k](e, id);
      }
      if (unsent) await send(id);
      pos = STEPS.length;
      spinStop();
      progressEl.textContent = 'end';
      instant = skipStep = holdNext = false; seek = -1;
      ended = true; sync();
    } catch (x) { if (!(x instanceof Abort)) throw x; }
  }

  playBtn.addEventListener('click', () => {
    if (ended) return play();
    if (release) return release();
    setPaused(!paused);
  });
  term.addEventListener('click', () => { if (release && pos === 0) release(); }); // start-up screen: click to open
  startBtn.addEventListener('click', () => play(1)); // turn 0: Claude Code open, no prompt yet, held
  endBtn.addEventListener('click', () => { instant = true; setPaused(false); autoscroll = true; if (release) release(); });
  const contBtn = $('cont');
  contBtn.addEventListener('click', () => {
    continuous = !continuous;
    contBtn.setAttribute('aria-pressed', String(continuous));
  });
  prevBtn.addEventListener('click', () => nav(-1));
  nextBtn.addEventListener('click', () => nav(1));
  document.addEventListener('keydown', (ev) => {
    if (ev.key === 'ArrowRight') nav(1);
    else if (ev.key === 'ArrowLeft') nav(-1);
  });
  document.querySelectorAll('[data-speed]').forEach((b) =>
    b.addEventListener('click', () => {
      setSpeed(+b.dataset.speed);
      document.querySelectorAll('[data-speed]').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
    })
  );

  const themeBtns = document.querySelectorAll('[data-theme-set]');
  const markTheme = (t) => themeBtns.forEach((x) => x.setAttribute('aria-pressed', String(x.dataset.themeSet === t)));
  function setTheme(t) {
    if (t === 'light' || t === 'dark') document.documentElement.dataset.theme = t;
    else document.documentElement.removeAttribute('data-theme');
    markTheme(t);
    try { localStorage.setItem('replay-theme', t); } catch (_) {}
  }
  themeBtns.forEach((b) => b.addEventListener('click', () => setTheme(b.dataset.themeSet)));
  let savedTheme = null;
  try { savedTheme = localStorage.getItem('replay-theme'); } catch (_) {}
  if (savedTheme) setTheme(savedTheme);
  else markTheme(document.documentElement.dataset.theme || 'system');

  play();
})();
