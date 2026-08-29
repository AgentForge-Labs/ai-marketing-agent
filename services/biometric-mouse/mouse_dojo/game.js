// game.js — Wassim Sayah

const MODE_DURATION = 5 * 60;
const MODES         = ['sniper', 'swarm', 'trace'];
const MODE_META = {
  sniper: { icon: 'S', name: 'Sniper Mode', color: '#5b6ef5',
            desc: 'Click the tiny targets. Precision and distance variety.' },
  swarm:  { icon: 'W', name: 'Swarm Mode',  color: '#f59e0b',
            desc: 'Click as many targets as fast as possible.' },
  trace:  { icon: 'T', name: 'Trace Mode',  color: '#22d3a0',
            desc: 'Follow the moving dot as closely as you can.' },
};

let modeIndex = 0, score = 0, combo = 1;
let modeTimer = MODE_DURATION;
let running   = false, animFrame = null, lastTick = null;

const BUCKETS = [
  { label: '0-100px',   min: 0,   max: 100,      count: 0, target: 80  },
  { label: '100-300px', min: 100, max: 300,      count: 0, target: 80  },
  { label: '300-600px', min: 300, max: 600,      count: 0, target: 60  },
  { label: '600px+',    min: 600, max: Infinity,  count: 0, target: 40  },
];

let mouseX = 0, mouseY = 0, prevX = 0, prevY = 0, totalSegments = 0;
let targets = [], traceDot = null, traceAngle = 0;

const canvas      = document.getElementById('gameCanvas');
const ctx         = canvas.getContext('2d');
const scoreEl     = document.getElementById('scoreVal');
const comboEl     = document.getElementById('comboVal');
const timerEl     = document.getElementById('timerVal');
const coverBar    = document.getElementById('coverageBar');
const coverPct    = document.getElementById('coveragePct');
const modeBadge   = document.getElementById('modeBadge');
const stopBtn     = document.getElementById('stopBtn');
const startScreen = document.getElementById('startScreen');
const transScreen = document.getElementById('transitionScreen');
const doneScreen  = document.getElementById('doneScreen');
const arena       = document.getElementById('arena');

function resizeCanvas() {
  canvas.width  = arena.clientWidth;
  canvas.height = arena.clientHeight;
}
window.addEventListener('resize', resizeCanvas);
resizeCanvas();

arena.addEventListener('mousemove', (e) => {
  const r = arena.getBoundingClientRect();
  mouseX = e.clientX - r.left;
  mouseY = e.clientY - r.top;
});

function recordMovement(x1, y1, x2, y2) {
  const dist = Math.hypot(x2 - x1, y2 - y1);
  if (dist < 5) return;
  totalSegments++;
  for (const b of BUCKETS) {
    if (dist >= b.min && dist < b.max) { b.count++; break; }
  }
  updateCoverage();
}

function coverageScore() {
  let filled = 0;
  for (const b of BUCKETS) filled += Math.min(b.count / b.target, 1);
  return Math.round((filled / BUCKETS.length) * 100);
}

function updateCoverage() {
  const pct = coverageScore();
  coverBar.style.width = pct + '%';
  coverPct.textContent = pct + '%';
  if (pct >= 100) coverPct.style.color = 'var(--green)';
}

function popEl(el) {
  el.classList.add('pop');
  setTimeout(() => el.classList.remove('pop'), 150);
}

function addScore(pts, x, y) {
  score += pts * combo;
  scoreEl.textContent = score.toLocaleString();
  popEl(scoreEl);
  const el = document.createElement('div');
  el.className = 'score-pop';
  el.textContent = '+' + pts * combo;
  el.style.left = x + 'px';
  el.style.top  = y + 'px';
  arena.appendChild(el);
  setTimeout(() => el.remove(), 800);
}

function showHitRing(x, y, r) {
  const el = document.createElement('div');
  el.className = 'hit-ring';
  el.style.cssText = `width:${r*2}px;height:${r*2}px;left:${x-r}px;top:${y-r}px;`;
  arena.appendChild(el);
  setTimeout(() => el.remove(), 500);
}

function fmtTime(sec) {
  return Math.floor(sec / 60) + ':' + String(Math.floor(sec % 60)).padStart(2, '0');
}

function setModeBadge(mode) {
  modeBadge.textContent = MODE_META[mode].name;
  modeBadge.className   = 'mode-badge ' + mode;
}

// sniper mode
function sniperSpawn() {
  const W = canvas.width, H = canvas.height;
  const r = 8 + Math.random() * 22;
  const m = r + 20;
  return {
    x: m + Math.random() * (W - 2*m), y: m + Math.random() * (H - 2*m),
    r, born: performance.now(), life: 2500 + Math.random() * 2000,
    alpha: 1, pulse: 0,
  };
}

function initSniper() {
  targets = [];
  for (let i = 0; i < 3; i++) targets.push(sniperSpawn());
}

function updateSniper(dt) {
  const now = performance.now();
  for (let i = targets.length - 1; i >= 0; i--) {
    const t = targets[i];
    t.alpha = Math.max(0, 1 - (now - t.born) / t.life);
    t.pulse += dt * 3;
    if (t.alpha <= 0) {
      targets.splice(i, 1);
      targets.push(sniperSpawn());
      combo = 1;
      comboEl.textContent = 'x1';
    }
  }
}

function drawSniper() {
  for (const t of targets) {
    ctx.save();
    ctx.globalAlpha = t.alpha;
    ctx.beginPath();
    ctx.arc(t.x, t.y, t.r + 6 + Math.sin(t.pulse) * 3, 0, Math.PI * 2);
    ctx.strokeStyle = 'rgba(91,110,245,0.25)';
    ctx.lineWidth = 1;
    ctx.stroke();
    const grad = ctx.createRadialGradient(t.x, t.y, 0, t.x, t.y, t.r);
    grad.addColorStop(0, '#7c91fa');
    grad.addColorStop(1, '#4050d0');
    ctx.beginPath();
    ctx.arc(t.x, t.y, t.r, 0, Math.PI * 2);
    ctx.fillStyle = grad;
    ctx.fill();
    ctx.strokeStyle = 'rgba(255,255,255,0.4)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(t.x - t.r * 0.5, t.y); ctx.lineTo(t.x + t.r * 0.5, t.y);
    ctx.moveTo(t.x, t.y - t.r * 0.5); ctx.lineTo(t.x, t.y + t.r * 0.5);
    ctx.stroke();
    ctx.restore();
  }
}

function clickSniper(x, y) {
  for (let i = targets.length - 1; i >= 0; i--) {
    const t = targets[i];
    if (Math.hypot(x - t.x, y - t.y) <= t.r + 4) {
      showHitRing(t.x, t.y, t.r);
      addScore(Math.round(100 / (t.r / 8)), x, y);
      combo = Math.min(combo + 1, 10);
      comboEl.textContent = 'x' + combo;
      popEl(comboEl);
      targets.splice(i, 1);
      targets.push(sniperSpawn());
      return;
    }
  }
  combo = 1;
  comboEl.textContent = 'x1';
}

// swarm mode
function swarmSpawn() {
  const W = canvas.width, H = canvas.height;
  const r = 14 + Math.random() * 14;
  const m = r + 10;
  const colors = ['#f59e0b', '#fb923c', '#f43f5e', '#a78bfa'];
  return {
    x: m + Math.random() * (W - 2*m), y: m + Math.random() * (H - 2*m),
    r, color: colors[Math.floor(Math.random() * colors.length)],
    born: performance.now(), life: 1200 + Math.random() * 1200,
    alpha: 0, scale: 0,
  };
}

function initSwarm() {
  targets = [];
  for (let i = 0; i < 8; i++) targets.push(swarmSpawn());
}

function updateSwarm(dt) {
  const now = performance.now();
  for (let i = targets.length - 1; i >= 0; i--) {
    const t = targets[i];
    const p = (now - t.born) / t.life;
    t.alpha = p < 0.1 ? p / 0.1 : Math.max(0, 1 - (p - 0.1) / 0.9);
    t.scale = p < 0.1 ? p / 0.1 : 1;
    if (now - t.born >= t.life) {
      targets.splice(i, 1);
      targets.push(swarmSpawn());
      combo = Math.max(1, combo - 1);
      comboEl.textContent = 'x' + combo;
    }
  }
}

function drawSwarm() {
  for (const t of targets) {
    ctx.save();
    ctx.globalAlpha = t.alpha;
    ctx.translate(t.x, t.y);
    ctx.scale(t.scale, t.scale);
    const grad = ctx.createRadialGradient(0, 0, 0, 0, 0, t.r);
    grad.addColorStop(0, t.color + 'ff');
    grad.addColorStop(1, t.color + '44');
    ctx.beginPath();
    ctx.arc(0, 0, t.r, 0, Math.PI * 2);
    ctx.fillStyle = grad;
    ctx.fill();
    ctx.restore();
  }
}

function clickSwarm(x, y) {
  for (let i = targets.length - 1; i >= 0; i--) {
    const t = targets[i];
    if (Math.hypot(x - t.x, y - t.y) <= t.r) {
      showHitRing(t.x, t.y, t.r);
      addScore(50, x, y);
      combo = Math.min(combo + 1, 15);
      comboEl.textContent = 'x' + combo;
      popEl(comboEl);
      targets.splice(i, 1);
      targets.push(swarmSpawn());
      return;
    }
  }
  combo = Math.max(1, combo - 1);
  comboEl.textContent = 'x' + combo;
}

// trace mode
function initTrace() {
  const W = canvas.width, H = canvas.height;
  traceAngle = 0;
  traceDot = {
    x: W / 2, y: H / 2, r: 14,
    cx: W / 2, cy: H / 2,
    orbitR: Math.min(W, H) * 0.3,
    speed: 0.8 + Math.random() * 0.4,
    wobbleA: Math.random() * Math.PI * 2,
    wobbleSpeed: 0.3,
  };
}

function updateTrace(dt) {
  if (!traceDot) return;
  traceAngle += traceDot.speed * dt;
  traceDot.wobbleA += traceDot.wobbleSpeed * dt;
  const wobble = Math.sin(traceDot.wobbleA) * 40;
  traceDot.x = traceDot.cx + Math.cos(traceAngle) * (traceDot.orbitR + wobble);
  traceDot.y = traceDot.cy + Math.sin(traceAngle * 1.3) * (traceDot.orbitR * 0.6 + wobble * 0.5);
  const dist = Math.hypot(mouseX - traceDot.x, mouseY - traceDot.y);
  if (dist < traceDot.r + 12) {
    score += Math.round(2 * combo);
    if (Math.floor(score / 500) > Math.floor((score - 2 * combo) / 500)) {
      combo = Math.min(combo + 1, 8);
      comboEl.textContent = 'x' + combo;
      popEl(comboEl);
    }
    scoreEl.textContent = score.toLocaleString();
  } else if (dist > traceDot.r + 60) {
    combo = Math.max(1, combo - dt * 0.5);
    comboEl.textContent = 'x' + Math.round(combo);
  }
}

function drawTrace() {
  if (!traceDot) return;
  const dist = Math.hypot(mouseX - traceDot.x, mouseY - traceDot.y);
  const on = dist < traceDot.r + 12;
  if (dist < 200) {
    ctx.beginPath();
    ctx.moveTo(mouseX, mouseY);
    ctx.lineTo(traceDot.x, traceDot.y);
    ctx.strokeStyle = `rgba(34,211,160,${Math.max(0, 0.15 - dist / 2000)})`;
    ctx.lineWidth = 1;
    ctx.stroke();
  }
  ctx.save();
  ctx.shadowColor = '#22d3a0';
  ctx.shadowBlur  = on ? 30 : 12;
  const grad = ctx.createRadialGradient(traceDot.x, traceDot.y, 0, traceDot.x, traceDot.y, traceDot.r);
  grad.addColorStop(0, on ? '#ffffff' : '#22d3a0');
  grad.addColorStop(1, '#0d8060');
  ctx.beginPath();
  ctx.arc(traceDot.x, traceDot.y, traceDot.r, 0, Math.PI * 2);
  ctx.fillStyle = grad;
  ctx.fill();
  ctx.restore();
  ctx.beginPath();
  ctx.arc(mouseX, mouseY, 5, 0, Math.PI * 2);
  ctx.strokeStyle = on ? '#22d3a0' : 'rgba(255,255,255,0.3)';
  ctx.lineWidth = 2;
  ctx.stroke();
}

function drawGrid() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.strokeStyle = 'rgba(30,34,53,0.6)';
  ctx.lineWidth = 1;
  const step = 60;
  for (let x = 0; x < canvas.width; x += step) {
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, canvas.height); ctx.stroke();
  }
  for (let y = 0; y < canvas.height; y += step) {
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(canvas.width, y); ctx.stroke();
  }
}

function drawModeAccent(mode) {
  ctx.save();
  ctx.strokeStyle = MODE_META[mode].color + '22';
  ctx.lineWidth = 3;
  ctx.strokeRect(2, 2, canvas.width - 4, canvas.height - 4);
  ctx.restore();
}

function tick(now) {
  if (!running) return;
  const dt = lastTick ? (now - lastTick) / 1000 : 0.016;
  lastTick = now;

  modeTimer -= dt;
  timerEl.textContent = fmtTime(Math.max(0, modeTimer));
  if (modeTimer <= 0) { nextMode(); return; }

  if (Math.hypot(mouseX - prevX, mouseY - prevY) > 5) {
    recordMovement(prevX, prevY, mouseX, mouseY);
    prevX = mouseX; prevY = mouseY;
  }

  drawGrid();
  const mode = MODES[modeIndex];
  drawModeAccent(mode);

  if (mode === 'sniper') { updateSniper(dt); drawSniper(); }
  if (mode === 'swarm')  { updateSwarm(dt);  drawSwarm();  }
  if (mode === 'trace')  { updateTrace(dt);  drawTrace();  }

  animFrame = requestAnimationFrame(tick);
}

function startMode(idx) {
  modeIndex = idx;
  modeTimer = MODE_DURATION;
  combo = 1;
  comboEl.textContent = 'x1';
  lastTick = null;
  setModeBadge(MODES[idx]);
  if (MODES[idx] === 'sniper') initSniper();
  if (MODES[idx] === 'swarm')  initSwarm();
  if (MODES[idx] === 'trace')  initTrace();
  stopBtn.classList.remove('hidden');
  running = true;
  animFrame = requestAnimationFrame(tick);
}

function nextMode() {
  running = false;
  cancelAnimationFrame(animFrame);
  if (modeIndex + 1 >= MODES.length) { showDone(); return; }
  showTransition(modeIndex + 1);
}

function showTransition(nextIdx) {
  const meta = MODE_META[MODES[nextIdx]];
  document.getElementById('transitionIcon').textContent  = meta.icon;
  document.getElementById('transitionTitle').textContent = meta.name;
  document.getElementById('transitionDesc').textContent  = meta.desc;
  transScreen.classList.remove('hidden');
  let n = 3;
  const el = document.getElementById('countdown');
  el.textContent = n;
  const iv = setInterval(() => {
    if (--n <= 0) { clearInterval(iv); transScreen.classList.add('hidden'); startMode(nextIdx); }
    else el.textContent = n;
  }, 1000);
}

function showDone() {
  running = false;
  stopBtn.classList.add('hidden');
  cancelAnimationFrame(animFrame);
  const pct = coverageScore();
  document.getElementById('finalStats').innerHTML = `
    <div class="final-stat"><div class="val">${score.toLocaleString()}</div><div class="lbl">FINAL SCORE</div></div>
    <div class="final-stat"><div class="val">${totalSegments}</div><div class="lbl">SEGMENTS</div></div>
    <div class="final-stat"><div class="val" style="color:${pct >= 80 ? 'var(--green)' : 'var(--orange)'}">${pct}%</div><div class="lbl">COVERAGE</div></div>
  `;
  document.getElementById('coverageDetail').innerHTML =
    '<div style="font-size:0.8rem;color:var(--text-dim);margin-bottom:10px;letter-spacing:1px;">DISTANCE COVERAGE</div>' +
    BUCKETS.map(b => `
      <div class="bucket-row">
        <span class="bucket-label">${b.label}</span>
        <div class="bucket-bar-wrap"><div class="bucket-bar-fill" style="width:${Math.min(100, (b.count / b.target) * 100)}%"></div></div>
        <span class="bucket-count">${b.count}/${b.target}</span>
      </div>
    `).join('');
  doneScreen.classList.remove('hidden');
}

stopBtn.addEventListener('click', () => {
  if (!running) return;
  running = false;
  cancelAnimationFrame(animFrame);
  showDone();
});

canvas.addEventListener('click', (e) => {
  if (!running) return;
  const r = arena.getBoundingClientRect();
  const x = e.clientX - r.left, y = e.clientY - r.top;
  if (MODES[modeIndex] === 'sniper') clickSniper(x, y);
  if (MODES[modeIndex] === 'swarm')  clickSwarm(x, y);
});

document.getElementById('startBtn').addEventListener('click', () => {
  startScreen.classList.add('hidden');
  showTransition(0);
});
