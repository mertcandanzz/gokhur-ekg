// =============================================
// EKG Monitor - Frontend
// =============================================

const $ = (s) => document.querySelector(s);
const canvas = $("#ekgCanvas");
const ctx = canvas.getContext("2d");

// DOM
const statusBadge = $("#statusBadge");
const statusText = $("#statusText");
const bpmEl = $("#bpm");
const signalEl = $("#signal");
const leadStatusEl = $("#leadStatus");
const ppsEl = $("#pps");
const leadOffEl = $("#leadOff");
const waitingEl = $("#waiting");
const simBtn = $("#simBtn");
const panicBtn = $("#panicBtn");
const panicFill = $("#panicFill");
const footerWs = $("#footerWs");

// State
let data = [];
let maxPoints = 800;
let isConnected = false;
let deviceConnected = false;
let simActive = false;
let packetCount = 0;
let lastPpsTime = Date.now();
let ws = null;

// Panic
let panicLevel = 0;
let panicHeld = false;

// BPM
let peaks = [];
let lastValue = 0;
let lastPeakTime = 0;
const BPM_THRESHOLD = 620;
let currentBpm = 0;

// ---- Canvas resize ----
function resize() {
  const r = canvas.getBoundingClientRect();
  canvas.width = r.width * devicePixelRatio;
  canvas.height = r.height * devicePixelRatio;
  ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
  maxPoints = Math.floor(r.width * 1.2);
}
window.addEventListener("resize", resize);
resize();

// ---- WebSocket ----
function connect() {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  const url = `${proto}//${location.host}/ws/client`;
  footerWs.textContent = url;

  ws = new WebSocket(url);

  ws.onopen = () => {
    isConnected = true;
    updateStatus();
  };

  ws.onclose = () => {
    isConnected = false;
    deviceConnected = false;
    simActive = false;
    updateStatus();
    updateSimBtn();
    setTimeout(connect, 2000);
  };

  ws.onerror = () => ws.close();

  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);

    if (msg.type === "device_status") {
      deviceConnected = msg.connected;
      if (msg.sim !== undefined) simActive = msg.sim;
      updateStatus();
      updateSimBtn();
      return;
    }

    if (msg.type === "ekg") {
      // Panic level guncelle
      if (msg.panic !== undefined) {
        panicLevel = msg.panic;
      } else {
        panicLevel = 0;
      }
      updatePanicUI();

      const values = msg.d;
      for (const v of values) {
        packetCount++;

        if (v === "!") {
          showLeadOff(true);
          leadStatusEl.textContent = "LEAD OFF";
          leadStatusEl.className = "stat-value err";
        } else {
          const num = parseInt(v);
          if (isNaN(num)) continue;

          showLeadOff(false);
          leadStatusEl.textContent = panicLevel > 0.3 ? "TASIKAR." : "OK";
          leadStatusEl.className = panicLevel > 0.3 ? "stat-value warn" : "stat-value accent";

          data.push(num);
          if (data.length > maxPoints) data.shift();

          signalEl.textContent = num;

          // BPM detection
          const now = Date.now();
          if (num > BPM_THRESHOLD && lastValue <= BPM_THRESHOLD) {
            if (now - lastPeakTime > 200) {
              peaks.push(now);
              lastPeakTime = now;
              if (peaks.length > 8) peaks.shift();
              if (peaks.length >= 3) {
                const intervals = [];
                for (let i = 1; i < peaks.length; i++) {
                  intervals.push(peaks[i] - peaks[i - 1]);
                }
                const avg =
                  intervals.reduce((a, b) => a + b, 0) / intervals.length;
                const bpm = Math.round(60000 / avg);
                if (bpm > 30 && bpm < 250) {
                  currentBpm = bpm;
                  bpmEl.innerHTML = `${bpm} <small>BPM</small>`;

                  // BPM renk
                  const bpmCard = bpmEl.closest(".stat-card");
                  if (bpm > 140) {
                    bpmEl.className = "stat-value err";
                    bpmCard.classList.add("danger");
                  } else if (bpm > 100) {
                    bpmEl.className = "stat-value warn";
                    bpmCard.classList.remove("danger");
                  } else {
                    bpmEl.className = "stat-value accent";
                    bpmCard.classList.remove("danger");
                  }
                }
              }
            }
          }
          lastValue = num;
        }
      }

      if (data.length > 0) {
        waitingEl.classList.add("hidden");
      }
    }
  };
}

// ---- UI updates ----
function updateStatus() {
  if (deviceConnected) {
    statusBadge.classList.add("connected");
    statusText.textContent = simActive ? "Simulasyon" : "Cihaz Bagli";
  } else if (isConnected) {
    statusBadge.classList.remove("connected");
    statusText.textContent = "Cihaz bekleniyor";
  } else {
    statusBadge.classList.remove("connected");
    statusText.textContent = "Sunucuya baglaniliyor";
  }
}

function showLeadOff(show) {
  leadOffEl.classList.toggle("show", show);
}

function updateSimBtn() {
  if (simActive) {
    simBtn.textContent = "Simulasyonu Durdur";
    simBtn.classList.add("active");
    panicBtn.classList.add("visible");
  } else {
    simBtn.textContent = "Simulasyon";
    simBtn.classList.remove("active");
    panicBtn.classList.remove("visible");
    panicLevel = 0;
    updatePanicUI();
  }
}

function updatePanicUI() {
  const pct = Math.round(panicLevel * 100);
  panicFill.style.width = pct + "%";

  if (panicLevel > 0.6) {
    panicBtn.classList.add("high");
    panicBtn.classList.remove("mid");
  } else if (panicLevel > 0.2) {
    panicBtn.classList.add("mid");
    panicBtn.classList.remove("high");
  } else {
    panicBtn.classList.remove("mid", "high");
  }
}

// ---- Sim button ----
simBtn.addEventListener("click", () => {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify({ cmd: simActive ? "sim_stop" : "sim_start" }));
});

// ---- Panic button (basili tut) ----
function panicStart(e) {
  e.preventDefault();
  if (!simActive || !ws || ws.readyState !== WebSocket.OPEN) return;
  panicHeld = true;
  ws.send(JSON.stringify({ cmd: "panic_on" }));
  panicBtn.classList.add("pressed");
}

function panicEnd(e) {
  e.preventDefault();
  if (!panicHeld) return;
  panicHeld = false;
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ cmd: "panic_off" }));
  }
  panicBtn.classList.remove("pressed");
}

panicBtn.addEventListener("mousedown", panicStart);
panicBtn.addEventListener("touchstart", panicStart);
window.addEventListener("mouseup", panicEnd);
window.addEventListener("touchend", panicEnd);

// PPS
setInterval(() => {
  const now = Date.now();
  const elapsed = (now - lastPpsTime) / 1000;
  if (elapsed > 0) {
    ppsEl.textContent = Math.round(packetCount / elapsed);
  }
  packetCount = 0;
  lastPpsTime = now;
}, 1000);

// ---- Draw ----
function draw() {
  const w = canvas.getBoundingClientRect().width;
  const h = canvas.getBoundingClientRect().height;

  ctx.clearRect(0, 0, w, h);

  // Grid
  const gridSize = 20;

  ctx.strokeStyle = "rgba(28, 28, 48, 0.6)";
  ctx.lineWidth = 0.5;
  for (let x = 0; x < w; x += gridSize) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, h);
    ctx.stroke();
  }
  for (let y = 0; y < h; y += gridSize) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
  }

  ctx.strokeStyle = "rgba(28, 28, 48, 1)";
  ctx.lineWidth = 0.8;
  for (let x = 0; x < w; x += gridSize * 5) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, h);
    ctx.stroke();
  }
  for (let y = 0; y < h; y += gridSize * 5) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
  }

  if (data.length < 2) {
    requestAnimationFrame(draw);
    return;
  }

  const padding = 24;
  const drawH = h - padding * 2;

  let min = Infinity, max = -Infinity;
  for (const v of data) {
    if (v < min) min = v;
    if (v > max) max = v;
  }
  const range = (max - min) || 1;
  const margin = range * 0.1;
  const scaleMin = min - margin;
  const scaleRange = (max + margin) - scaleMin;

  // Renk: panik seviyesine gore
  const lineR = Math.round(0 + panicLevel * 255);
  const lineG = Math.round(228 - panicLevel * 164);
  const lineB = Math.round(176 - panicLevel * 64);
  const lineColor = `rgb(${lineR}, ${lineG}, ${lineB})`;
  const glowColor = `rgba(${lineR}, ${lineG}, ${lineB}, 0.12)`;
  const dotGlow = `rgba(${lineR}, ${lineG}, ${lineB}, 0.25)`;

  // Glow
  ctx.beginPath();
  ctx.strokeStyle = glowColor;
  ctx.lineWidth = 8;
  ctx.lineJoin = "round";
  ctx.lineCap = "round";
  for (let i = 0; i < data.length; i++) {
    const x = (i / maxPoints) * w;
    const y = padding + drawH - ((data[i] - scaleMin) / scaleRange) * drawH;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.stroke();

  // Main line
  ctx.beginPath();
  ctx.strokeStyle = lineColor;
  ctx.lineWidth = 2;
  ctx.lineJoin = "round";
  ctx.lineCap = "round";
  for (let i = 0; i < data.length; i++) {
    const x = (i / maxPoints) * w;
    const y = padding + drawH - ((data[i] - scaleMin) / scaleRange) * drawH;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.stroke();

  // Cursor dot
  if (data.length > 0) {
    const lastIdx = data.length - 1;
    const lx = (lastIdx / maxPoints) * w;
    const ly = padding + drawH - ((data[lastIdx] - scaleMin) / scaleRange) * drawH;

    ctx.beginPath();
    ctx.arc(lx, ly, 10, 0, Math.PI * 2);
    ctx.fillStyle = dotGlow;
    ctx.fill();

    ctx.beginPath();
    ctx.arc(lx, ly, 3.5, 0, Math.PI * 2);
    ctx.fillStyle = lineColor;
    ctx.fill();
  }

  requestAnimationFrame(draw);
}

// ---- Init ----
connect();
draw();
