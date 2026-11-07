/* Chiz va Top -- Telegram Mini App klienti.
 *
 * Uch qism: Telegram bilan bog'lanish, WebSocket (qayta ulanish bilan),
 * va canvas. Koordinatalar har doim 0..1 oralig'ida yuboriladi, shunda
 * turli o'lchamdagi telefonlarda rasm bir xil chiqadi.
 */

// @BotFather da bot va mini-app yaratgach shuni to'ldiring:
const APP_LINK = "https://t.me/YOUR_BOT/play";

const tg = window.Telegram && window.Telegram.WebApp;
const $ = (id) => document.getElementById(id);

const state = {
  ws: null, code: null, you: null, drawer: null, phase: "lobby",
  lang: "uz", strokes: [], color: "#302b24", penColor: "#302b24", width: 4,
  eraser: false, retries: 0, closing: false,
};

const PAPER_INK = "#fffdf7";   // o'chirg'ich = qog'oz rangi bilan chizish

/* ---------------------------------------------------------------- Telegram */

if (tg) {
  tg.ready();
  tg.expand();
  // Telegram'dan faqat yorug'/qorong'i tanlovini olamiz, ranglarini emas --
  // daftar palitrasi o'yinning o'z ko'rinishi.
  //
  // Diqqat: telegram-web-app.js oddiy brauzerda ham yuklanadi va o'shanda
  // colorScheme doim "light" deydi. Unga ishonsak, brauzerning o'z qorong'i
  // rejimini bosib qo'yamiz. Shuning uchun avval haqiqatan Telegram ichida
  // ekanimizni tekshiramiz: tashqarida platform "unknown" bo'ladi.
  const inTelegram = !!tg.platform && tg.platform !== "unknown";
  const applyTheme = () => {
    if (inTelegram && tg.colorScheme) {
      document.documentElement.dataset.theme = tg.colorScheme;
    }
  };
  applyTheme();
  if (inTelegram && tg.onEvent) tg.onEvent("themeChanged", applyTheme);
}

function initData() {
  return (tg && tg.initData) || "";
}

function startParam() {
  if (tg && tg.initDataUnsafe && tg.initDataUnsafe.start_param) {
    return tg.initDataUnsafe.start_param;
  }
  return new URLSearchParams(location.search).get("room") || "";
}

function roomLink() {
  if (APP_LINK.indexOf("YOUR_BOT") === -1) return APP_LINK + "?startapp=" + state.code;
  return location.origin + location.pathname + "?room=" + state.code; // brauzerda sinash uchun
}

/* -------------------------------------------------------------- ekranlar */

function show(name) {
  ["start", "wait", "game", "end"].forEach((s) => {
    $("screen-" + s).classList.toggle("hidden", s !== name);
  });
}

let toastTimer = null;
function toast(text) {
  const el = $("toast");
  el.textContent = text;
  el.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add("hidden"), 2200);
}

function logLine(text, cls) {
  const el = document.createElement("div");
  if (cls) el.className = cls;
  el.textContent = text;
  $("log").prepend(el);
  while ($("log").children.length > 6) $("log").lastChild.remove();
}

/* ------------------------------------------------------------- WebSocket */

function connect(room) {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  // Yo'lga nisbatan: ildizda "/ws", yo'l ostida esa "/chiz/ws". Shunda
  // o'yinni mavjud domenning bir qismi sifatida ham qo'yish mumkin --
  // yangi subdomen va yangi sertifikat kerak bo'lmaydi.
  const base = location.pathname.replace(/[^/]*$/, "");
  const ws = new WebSocket(proto + "//" + location.host + base + "ws");
  state.ws = ws;

  ws.onopen = () => {
    state.retries = 0;
    const join = { type: "join", initData: initData(), lang: state.lang };
    if (room) join.room = room;
    const dev = new URLSearchParams(location.search).get("dev_user");
    if (dev) join.dev_user = dev;
    ws.send(JSON.stringify(join));
  };

  ws.onmessage = (ev) => handle(JSON.parse(ev.data));

  ws.onclose = () => {
    if (state.closing) return;
    // Telegram webview'da ulanish muntazam uziladi: fon, tarmoq almashuvi.
    // Shuning uchun ortib boruvchi kechikish bilan o'zimiz qaytib ulanamiz.
    state.retries += 1;
    const delay = Math.min(800 * Math.pow(1.6, state.retries - 1), 8000);
    if (state.retries === 2) toast("Qayta ulanmoqda...");
    setTimeout(() => connect(state.code || room), delay);
  };
}

function sendMsg(obj) {
  if (state.ws && state.ws.readyState === WebSocket.OPEN) {
    state.ws.send(JSON.stringify(obj));
  }
}

function handle(msg) {
  switch (msg.type) {
    case "joined":
      state.code = msg.code;
      state.you = msg.you;
      $("room-code").textContent = msg.code.toUpperCase();
      break;

    case "state":
      applyState(msg);
      break;

    case "stroke":
      state.strokes.push(msg.stroke);
      drawStroke(msg.stroke);
      break;

    case "clear":
      state.strokes = [];
      redraw();
      break;

    case "replay_strokes":
      state.strokes = msg.strokes || [];
      redraw();
      break;

    case "mask":
      if (state.you !== state.drawer) $("wordbar").textContent = msg.mask;
      break;

    case "time":
      setTimer(msg.remaining);
      break;

    case "guess":
      if (msg.correct) {
        logLine("Topildi: " + msg.text, "ok");
      } else if (msg.by === state.you) {
        if (msg.close) logLine(msg.text + " \u2014 yaqin!", "near");
        const input = $("guess");
        input.classList.remove("wrong");
        void input.offsetWidth;
        input.classList.add("wrong");
      } else {
        logLine(msg.text);
      }
      break;

    case "round_end":
      showCurtain(msg);
      break;

    case "error":
      toast(msg.error);
      break;
  }
}

function applyState(s) {
  const wasRound = state.round;
  state.phase = s.phase;
  state.drawer = s.drawer;
  state.round = s.round;

  if (s.phase === "lobby") {
    show("wait");
    return;
  }
  if (s.phase === "game_end") {
    showEnd(s);
    return;
  }

  show("game");
  if (s.round !== wasRound) {
    state.strokes = [];
    redraw();
    $("log").innerHTML = "";
  }

  const youDraw = s.you === s.drawer;
  $("tools").classList.toggle("hidden", !youDraw);
  $("guessbar").classList.toggle("hidden", youDraw);
  $("canvas").style.cursor = youDraw ? "crosshair" : "default";

  $("round-label").textContent = "raund " + s.round + " / " + s.total_rounds;
  const them = s.players.filter((p) => p.id !== s.you)[0];
  setScore("score-you", s.scores[s.you] || 0);
  setScore("score-them", them ? (s.scores[them.id] || 0) : 0);
  setTimer(s.remaining);

  const bar = $("wordbar");
  const showWord = s.phase === "round_end" || youDraw;
  bar.textContent = showWord ? s.word : (s.mask || "");
  bar.classList.toggle("secret", youDraw && s.phase === "drawing");

  if (them && !them.connected) toast(them.name + " uzildi...");
}

function setScore(id, value) {
  const el = $(id);
  const before = parseInt(el.textContent, 10) || 0;
  el.textContent = value;
  if (value > before) {
    el.classList.remove("bump");
    void el.offsetWidth;          // animatsiyani qaytadan boshlash uchun
    el.classList.add("bump");
  }
}

function showCurtain(msg) {
  $("curtain-word").textContent = msg.word || "";
  const who = msg.guessed_by;
  $("curtain-who").innerHTML = "";
  const line = document.createElement("span");
  if (!who) line.textContent = "Hech kim topmadi";
  else if (who === state.you) { line.innerHTML = "<b>Siz topdingiz</b>"; }
  else line.textContent = "Raqibingiz topdi";
  $("curtain-who").append(line);
  $("curtain").classList.remove("hidden");
  clearTimeout(curtainTimer);
  curtainTimer = setTimeout(() => $("curtain").classList.add("hidden"), 2600);
}
let curtainTimer = null;

function setTimer(seconds) {
  const v = Math.max(0, Math.ceil(seconds || 0));
  $("timer").textContent = v;
  $("timer").classList.toggle("low", v <= 10);
}

function showEnd(s) {
  show("end");
  const you = s.scores[s.you] || 0;
  const them = s.players.filter((p) => p.id !== s.you)[0];
  const theirs = them ? (s.scores[them.id] || 0) : 0;
  $("end-title").textContent =
    you > theirs ? "Siz yutdingiz!" : you < theirs ? "Yutqazdingiz" : "Durang";
  $("end-scores").innerHTML = "";
  [[ "Siz", you, you >= theirs ], [ them ? them.name : "Raqib", theirs, theirs >= you ]]
    .forEach(([name, score, win]) => {
      const row = document.createElement("div");
      row.className = "row" + (win && you !== theirs ? " win" : "");
      row.innerHTML = "<span></span><span></span>";
      row.children[0].textContent = name;
      row.children[1].textContent = score;
      $("end-scores").append(row);
    });
}

/* ----------------------------------------------------------------- canvas */

const canvas = $("canvas");
const ctx = canvas.getContext("2d");

function sizeCanvas() {
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.round(rect.width * dpr);
  canvas.height = Math.round(rect.height * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  redraw();
}

function redraw() {
  const rect = canvas.getBoundingClientRect();
  ctx.clearRect(0, 0, rect.width, rect.height);
  ctx.fillStyle = PAPER_INK;
  ctx.fillRect(0, 0, rect.width, rect.height);
  state.strokes.forEach(drawStroke);
}

function drawStroke(stroke) {
  if (!stroke || !stroke.p || stroke.p.length === 0) return;
  const rect = canvas.getBoundingClientRect();
  ctx.strokeStyle = stroke.c || "#111827";
  ctx.lineWidth = (stroke.w || 4) * (rect.width / 320); // nisbiy qalinlik
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.beginPath();
  stroke.p.forEach(([x, y], i) => {
    const px = x * rect.width, py = y * rect.height;
    if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
  });
  if (stroke.p.length === 1) {
    const [x, y] = stroke.p[0];
    ctx.lineTo(x * rect.width + 0.1, y * rect.height);
  }
  ctx.stroke();
}

let current = null;        // chizilayotgan chiziq (hali tugamagan)
let currentId = 0;         // bir chiziqning hamma bo'laklari shu id bilan ketadi
let sentUpTo = 0;          // shu nuqtagacha yuborilgan
let flushTimer = null;

function point(ev) {
  const rect = canvas.getBoundingClientRect();
  return [
    Math.min(1, Math.max(0, (ev.clientX - rect.left) / rect.width)),
    Math.min(1, Math.max(0, (ev.clientY - rect.top) / rect.height)),
  ];
}

function canDraw() {
  return state.phase === "drawing" && state.you === state.drawer;
}

canvas.addEventListener("pointerdown", (ev) => {
  if (!canDraw()) return;
  canvas.setPointerCapture(ev.pointerId);
  currentId += 1;
  sentUpTo = 0;
  const width = state.eraser ? state.width * 3 : state.width;
  current = { id: state.you + ":" + currentId, c: state.color, w: width, p: [point(ev)] };
  drawStroke(current);
});

canvas.addEventListener("pointermove", (ev) => {
  if (!current) return;
  current.p.push(point(ev));
  drawStroke({ c: current.c, w: current.w, p: current.p.slice(-2) });
  // Har `pointermove` da emas, 50ms da bir marta. Aks holda mobil
  // ulanish nuqtalar oqimiga ko'milib qoladi.
  if (!flushTimer) flushTimer = setTimeout(flush, 50);
});

function flush() {
  flushTimer = null;
  if (!current || current.p.length <= sentUpTo) return;
  // Bitta nuqta ustma-ust ketadi, shunda bo'laklar orasida uzilish ko'rinmaydi.
  const from = Math.max(0, sentUpTo - 1);
  const segment = { id: current.id, c: current.c, w: current.w, p: current.p.slice(from) };
  sentUpTo = current.p.length;
  state.strokes.push(segment);   // mahalliy holat serverdagi bilan bir xil bo'ladi
  sendMsg({ type: "stroke", stroke: segment });
}

function endStroke() {
  if (!current) return;
  clearTimeout(flushTimer);
  flushTimer = null;
  flush();
  current = null;
  sentUpTo = 0;
}
canvas.addEventListener("pointerup", endStroke);
canvas.addEventListener("pointercancel", endStroke);
canvas.addEventListener("pointerleave", endStroke);

function undoLast() {
  if (state.strokes.length === 0) return;
  const id = state.strokes[state.strokes.length - 1].id;
  while (state.strokes.length && state.strokes[state.strokes.length - 1].id === id) {
    state.strokes.pop();
  }
  redraw();
}

/* ------------------------------------------------------------- boshqaruv */

function setEraser(on) {
  state.eraser = on;
  $("btn-eraser").classList.toggle("on", on);
  state.color = on ? PAPER_INK : state.penColor;
}

document.querySelectorAll(".swatch").forEach((b) => {
  b.addEventListener("click", () => {
    document.querySelectorAll(".swatch").forEach((x) => x.classList.remove("on"));
    b.classList.add("on");
    state.penColor = b.dataset.color;
    setEraser(false);
  });
});

document.querySelectorAll(".size").forEach((b) => {
  b.addEventListener("click", () => {
    document.querySelectorAll(".size").forEach((x) => x.classList.remove("on"));
    b.classList.add("on");
    state.width = parseInt(b.dataset.width, 10);
  });
});

$("btn-eraser").addEventListener("click", () => setEraser(!state.eraser));

document.querySelectorAll(".lang").forEach((b) => {
  b.addEventListener("click", () => {
    document.querySelectorAll(".lang").forEach((x) => x.classList.remove("on"));
    b.classList.add("on");
    state.lang = b.dataset.lang;
  });
});

$("btn-clear").addEventListener("click", () => {
  if (!canDraw()) return;
  state.strokes = [];
  redraw();
  sendMsg({ type: "clear" });
});

$("btn-undo").addEventListener("click", () => {
  if (!canDraw()) return;
  undoLast();
  sendMsg({ type: "undo" });
});

$("btn-new").addEventListener("click", () => {
  show("wait");
  connect(null);
});

$("btn-share").addEventListener("click", () => {
  const link = roomLink();
  const text = "Chiz va Top o'ynaymizmi?";
  const share = "https://t.me/share/url?url=" + encodeURIComponent(link) +
                "&text=" + encodeURIComponent(text);
  if (tg && tg.openTelegramLink) tg.openTelegramLink(share);
  else window.open(share, "_blank");
});

$("btn-copy").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(roomLink());
    toast("Havola nusxalandi");
  } catch (e) {
    toast(roomLink());
  }
});

function submitGuess() {
  const input = $("guess");
  const text = input.value.trim();
  if (!text) return;
  sendMsg({ type: "guess", text: text });
  input.value = "";
}
$("btn-guess").addEventListener("click", submitGuess);
$("guess").addEventListener("keydown", (ev) => {
  if (ev.key === "Enter") submitGuess();
});

$("btn-replay").addEventListener("click", () => sendMsg({ type: "replay" }));

window.addEventListener("resize", sizeCanvas);
window.addEventListener("beforeunload", () => { state.closing = true; });

/* ---------------------------------------------------------------- ishga tushish */

sizeCanvas();
const joining = startParam();
if (joining) {
  show("wait");
  connect(joining);
} else {
  show("start");
}
