// Runs inside the filmed page (an init script). Stands in for the tab a student would share: navigator.mediaDevices
// .getDisplayMedia returns a 1920×1080 "lecture player" drawn on a canvas (a chalkboard being written on, the
// teacher's camera, player controls) plus the teacher's voice. Everything Focs does with it (cropping, change
// detection, OCR, notes, captions) is the real app on the real server.
// window.__LECTURE = { audio, teacher, title, boards: [{ start, end, lines: [..] }], speech: [[start, end], ..] }
(() => {
  const W = 1920, H = 1080;
  const BOARD = { x: 40, y: 40, w: 1360, h: 860 };
  const CAM = { x: 1440, y: 40, w: 440, h: 270 };
  const ease = (t) => (t < 0 ? 0 : t > 1 ? 1 : 1 - Math.pow(1 - t, 2));

  function texture() {
    const c = document.createElement("canvas"); c.width = BOARD.w; c.height = BOARD.h;
    const g = c.getContext("2d");
    const grad = g.createRadialGradient(BOARD.w * 0.45, BOARD.h * 0.4, 100, BOARD.w * 0.5, BOARD.h * 0.5, BOARD.w * 0.75);
    grad.addColorStop(0, "#26332c"); grad.addColorStop(1, "#18211c");
    g.fillStyle = grad; g.fillRect(0, 0, BOARD.w, BOARD.h);
    let seed = 7; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
    for (let i = 0; i < 70; i++) {  // old chalk smudges
      g.fillStyle = `rgba(255,255,255,${0.012 + rnd() * 0.02})`;
      g.beginPath(); g.ellipse(rnd() * BOARD.w, rnd() * BOARD.h, 40 + rnd() * 160, 8 + rnd() * 30, rnd() * 3, 0, 7); g.fill();
    }
    for (let i = 0; i < 2500; i++) { g.fillStyle = `rgba(255,255,255,${rnd() * 0.05})`; g.fillRect(rnd() * BOARD.w, rnd() * BOARD.h, 1.5, 1.5); }
    return c;
  }

  function lineFont(i) { return i === 0 ? "600 74px 'Segoe Print', 'Comic Sans MS', cursive" : "62px 'Segoe Print', 'Comic Sans MS', cursive"; }
  const charTime = 0.075;

  function drawBoard(g, tex, board, t) {
    g.drawImage(tex, BOARD.x, BOARD.y);
    if (!board) return null;
    let head = null;
    board.lines.forEach((text, i) => {
      const start = board.start + (board.at ? board.at[i] : i * 3.4);
      const dur = Math.max(1.3, text.length * charTime);
      const k = ease((t - start) / dur);
      if (k <= 0) return;
      g.font = lineFont(i);
      const x = BOARD.x + 90, y = BOARD.y + 150 + i * 165;
      const w = g.measureText(text).width;
      g.save();
      g.beginPath(); g.rect(x - 10, y - 90, (w + 20) * k, 140); g.clip();
      g.fillStyle = "rgba(246,244,236,0.94)"; g.shadowColor = "rgba(255,255,255,0.25)"; g.shadowBlur = 3;
      g.fillText(text, x, y);
      if (i === 0) { g.fillRect(x, y + 22, w, 4); }
      g.restore();
      if (k < 1) head = [x + w * k, y - 18 + Math.sin(t * 22) * 6];
    });
    // the eraser at the end of a board
    if (board.end && t > board.end) {
      const k = Math.min(1, (t - board.end) / 1.3);
      const ex = BOARD.x + BOARD.w * k;
      g.drawImage(tex, 0, 0, ex - BOARD.x, BOARD.h, BOARD.x, BOARD.y, ex - BOARD.x, BOARD.h);
      g.fillStyle = "#3b2f25"; g.fillRect(ex - 40, BOARD.y + 300 + Math.sin(t * 9) * 120, 80, 150);
      g.fillStyle = "#e9e3d5"; g.fillRect(ex - 40, BOARD.y + 300 + Math.sin(t * 9) * 120 + 120, 80, 30);
    }
    return head;
  }

  function drawChalk(g, head) {
    if (!head) return;
    g.save(); g.translate(head[0] + 10, head[1] + 6); g.rotate(-0.6);
    g.fillStyle = "#f1eee4"; g.fillRect(0, -7, 54, 14);
    g.fillStyle = "rgba(0,0,0,0.25)"; g.fillRect(0, 4, 54, 3);
    g.restore();
  }

  function drawCam(g, t, speaking, cfg) {
    const { x, y, w, h } = CAM;
    const grad = g.createLinearGradient(x, y, x, y + h); grad.addColorStop(0, "#5b6670"); grad.addColorStop(1, "#2f363c");
    g.fillStyle = grad; g.fillRect(x, y, w, h);
    g.fillStyle = "#c8b48a"; g.fillRect(x + 20, y + 30, 120, 80);  // a shelf behind her
    const cx = x + w / 2 + Math.sin(t * 1.3) * 6, cy = y + 120;
    g.fillStyle = "#7a2f4a"; g.beginPath(); g.ellipse(cx, y + h + 10, 150, 95, 0, Math.PI, 0); g.fill();  // kurta
    g.fillStyle = "#b07a55"; g.fillRect(cx - 22, cy + 40, 44, 50);  // neck
    g.fillStyle = "#1c1412"; g.beginPath(); g.ellipse(cx, cy - 8, 66, 78, 0, 0, 7); g.fill();  // hair
    g.fillStyle = "#c58c62"; g.beginPath(); g.ellipse(cx, cy + 6, 52, 62, 0, 0, 7); g.fill();  // face
    g.fillStyle = "#1c1412"; g.beginPath(); g.ellipse(cx, cy - 46, 56, 26, 0, Math.PI, 0); g.fill();
    g.fillStyle = "#2a1a14"; g.beginPath(); g.arc(cx - 19, cy - 2, 5, 0, 7); g.arc(cx + 19, cy - 2, 5, 0, 7); g.fill();
    g.strokeStyle = "#2a1a14"; g.lineWidth = 3; g.beginPath(); g.arc(cx - 19, cy - 2, 13, 0, 7); g.stroke(); g.beginPath(); g.arc(cx + 19, cy - 2, 13, 0, 7); g.stroke();
    const open = speaking ? 3 + Math.abs(Math.sin(t * 13)) * 9 : 2;
    g.fillStyle = "#6b2a22"; g.beginPath(); g.ellipse(cx, cy + 32, 13, open, 0, 0, 7); g.fill();
    g.fillStyle = "rgba(0,0,0,0.55)"; g.fillRect(x, y + h - 40, w, 40);
    g.fillStyle = "#fff"; g.font = "600 22px 'Segoe UI', Arial"; g.fillText(cfg.teacher, x + 16, y + h - 13);
  }

  function drawChrome(g, t, cfg) {
    g.fillStyle = "#e23b2e"; g.beginPath(); g.roundRect(1440, 340, 92, 34, 6); g.fill();
    g.fillStyle = "#fff"; g.font = "700 18px 'Segoe UI', Arial"; g.fillText("● LIVE", 1453, 364);
    g.fillStyle = "#f2f2f2"; g.font = "600 30px 'Segoe UI', Arial"; g.fillText(cfg.title, 1440, 420);
    g.fillStyle = "#9a9a9a"; g.font = "22px 'Segoe UI', Arial"; g.fillText(cfg.subtitle, 1440, 456);
    g.fillStyle = "#cfcfcf"; g.font = "600 20px 'Segoe UI', Arial"; g.fillText("UP NEXT", 1440, 540);
    ["Torque on a rigid body", "Angular momentum", "Rolling on an incline", "Practice: 15 PYQs"].forEach((s, i) => {
      g.fillStyle = "#262626"; g.fillRect(1440, 560 + i * 82, 120, 66);
      g.fillStyle = "#c9c9c9"; g.font = "21px 'Segoe UI', Arial"; g.fillText(s, 1576, 600 + i * 82);
    });
    // player controls
    const played = 0.27 + t / 3200;
    g.fillStyle = "#3a3a3a"; g.fillRect(40, 940, 1840, 6);
    g.fillStyle = "#e23b2e"; g.fillRect(40, 940, 1840 * played, 6);
    g.beginPath(); g.arc(40 + 1840 * played, 943, 10, 0, 7); g.fill();
    g.fillStyle = "#eee"; g.fillRect(60, 975, 10, 34); g.fillRect(80, 975, 10, 34);  // pause
    const secs = 872 + Math.floor(t), mm = Math.floor(secs / 60), ss = String(secs % 60).padStart(2, "0");
    g.font = "22px 'Segoe UI', Arial"; g.fillText(`${mm}:${ss} / 52:10`, 130, 1001);
    g.fillText("CC    1080p    ⚙    ⛶", 1640, 1001);
  }

  let made = null;
  async function displayMedia() {
    if (made) return made.clone();
    const cfg = window.__LECTURE;
    const canvas = document.createElement("canvas"); canvas.width = W; canvas.height = H;
    const g = canvas.getContext("2d");
    const tex = texture();
    const t0 = performance.now();
    const draw = () => {
      const t = (performance.now() - t0) / 1000;
      g.fillStyle = "#0e0e0e"; g.fillRect(0, 0, W, H);
      const board = [...cfg.boards].reverse().find((b) => t >= b.start - 0.5) || null;
      const head = drawBoard(g, tex, board, t);
      g.strokeStyle = "#5a4a3a"; g.lineWidth = 10; g.strokeRect(BOARD.x - 5, BOARD.y - 5, BOARD.w + 10, BOARD.h + 10);
      drawChalk(g, head);
      drawCam(g, t, cfg.speech.some(([a, b]) => t >= a && t <= b), cfg);
      drawChrome(g, t, cfg);
    };
    draw();
    setInterval(draw, 33);
    const video = canvas.captureStream(30);
    const tracks = [...video.getVideoTracks()];
    if (cfg.audio) {
      const ctx = new AudioContext();
      const dest = ctx.createMediaStreamDestination();
      tracks.push(...dest.stream.getAudioTracks());
      fetch(cfg.audio).then((r) => r.arrayBuffer()).then((b) => ctx.decodeAudioData(b)).then((buf) => {
        const src = ctx.createBufferSource(); src.buffer = buf; src.connect(dest);
        src.start(0, Math.max(0, (performance.now() - t0) / 1000));
      }).catch((e) => console.warn("lecture audio:", e));
    }
    made = new MediaStream(tracks);
    window.__lectureT0 = t0;
    return made;
  }

  const md = navigator.mediaDevices;
  if (md) md.getDisplayMedia = () => new Promise((ok) => setTimeout(() => ok(displayMedia()), 700));
})();
