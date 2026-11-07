import { createRun, restartRun, stepRun, command, SUMMON_DURATION } from "./run.js";
import { createScene, zoneName } from "./scene.js";

const $ = (id) => document.getElementById(id);
const ui = Object.fromEntries([
  "game", "viewport", "start-screen", "start", "start-label", "load-note", "menu-best",
  "zone-name", "hud", "pause", "distance", "best",
  "rice", "shield", "summon", "summon-cut-in", "skill-status", "energy", "coach", "notice",
  "dialog", "dialog-title", "dialog-description", "dialog-primary", "result",
  "result-distance", "result-rice", "home",
].map((id) => [id, $(id)]));

const RECORD_KEY = "fish-run-web-best";
const SUMMON_CUT_IN = 1.15;
const FAILURE_HINTS = {
  train: "撞上列车了。看到车灯时，提前换到旁边的车道。",
  jump: "撞上低路障了。看到橙色上箭头时，按空格跳过去。",
  slide: "撞上横杆了。看到黄色下箭头时，按 ↓ 翻滚通过。",
};
const KEYS = {
  ArrowLeft: "left", KeyA: "left", ArrowRight: "right", KeyD: "right",
  Space: "jump", ArrowUp: "jump", KeyW: "jump",
  ArrowDown: "roll", KeyS: "roll", KeyQ: "summon",
};

let best = 0;
try { best = Math.max(0, Number(localStorage.getItem(RECORD_KEY)) || 0); } catch { /* optional storage */ }

let run = createRun();
let loaded = false;
let shownPhase = null;
let messageUntil = 0;
let hitKind = null;
let wasFlashing = false;

function text(node, value) {
  const output = String(value);
  if (node.textContent !== output) node.textContent = output;
}

function showNotice(message) {
  text(ui.notice, message);
  messageUntil = run.elapsed + 1.7;
}

function start() {
  if (!loaded) return;
  restartRun(run);
  messageUntil = 0;
  hitKind = null;
  wasFlashing = false;
  syncUI();
}

function doAction(action) {
  if (action === "summon") {
    if (command(run, action)) {
      messageUntil = 0;
      syncUI();
    } else if (run.phase === "running" && !run.summonRemaining) {
      showNotice("再吃几口白饭补算力");
    }
    return;
  }
  command(run, action);
}

function togglePause() {
  if (run.phase === "running") command(run, "pause");
  else if (run.phase === "paused") command(run, "resume");
  syncUI();
}

function syncPhase() {
  const phase = run.phase;
  if (phase === shownPhase) return;
  shownPhase = phase;
  const ready = phase === "ready";
  const ended = phase === "over";
  const overlay = phase === "paused" || ended;
  ui["start-screen"].hidden = !ready;
  ui.hud.hidden = ready;
  ui.pause.hidden = phase !== "running";
  ui.dialog.hidden = !overlay;
  ui.result.hidden = !ended;
  if (ended && run.distance > best) {
    best = Math.floor(run.distance);
    try { localStorage.setItem(RECORD_KEY, String(best)); } catch { /* optional storage */ }
  }
  if (overlay) {
    text(ui["dialog-title"], ended ? "先歇一口。" : "摸鱼时间");
    text(ui["dialog-description"], ended ? (FAILURE_HINTS[run.failure] ?? "再试一次吧。") : "按空格或 Esc 回到赛道。");
    text(ui["dialog-primary"], ended ? "再跑一次" : "继续跑");
    text(ui["result-distance"], `${Math.floor(run.distance)} m`);
    text(ui["result-rice"], run.rice);
    ui["dialog-primary"].focus({ preventScroll: true });
  }
}

function syncUI() {
  syncPhase();
  const cutIn = ui["summon-cut-in"];
  const paused = run.phase === "paused";
  const cutInActive = (run.phase === "running" || paused) &&
    run.summonRemaining > SUMMON_DURATION - SUMMON_CUT_IN;
  if (cutIn.hidden === cutInActive) cutIn.hidden = !cutInActive;
  cutIn.toggleAttribute("data-paused", cutInActive && paused);
  if (run.phase === "ready") {
    text(ui["menu-best"], best);
    ui.coach.hidden = true;
    ui.notice.hidden = true;
    return;
  }
  text(ui.distance, Math.floor(run.distance));
  const zone = zoneName(run.distance);
  if (ui["zone-name"].textContent !== zone) {
    text(ui["zone-name"], zone);
    ui.game.dataset.zone = zone;
    ui.viewport.setAttribute("aria-label", `${zone}三维赛道`);
  }
  text(ui.best, best);
  text(ui.rice, run.rice);
  text(ui.shield, run.shield ? "护盾 × 1" : "护盾已用");
  text(ui["skill-status"], run.summonRemaining ? `救场中 ${run.summonRemaining.toFixed(1)} s` : `算力 ${run.energy}%`);
  const energyWidth = `${run.energy}%`;
  if (ui.energy.style.width !== energyWidth) ui.energy.style.width = energyWidth;
  const summonReady = run.phase === "running" && run.energy >= 100 && !run.summonRemaining;
  ui.summon.disabled = !summonReady;
  ui.summon.classList.toggle("ready", summonReady);
  ui.coach.hidden = run.phase !== "running" || run.elapsed > 9;
  ui.notice.hidden = run.phase !== "running" || run.elapsed >= messageUntil;
}

ui.start.addEventListener("click", start);
ui.pause.addEventListener("click", togglePause);
ui.summon.addEventListener("click", () => doAction("summon"));
ui["dialog-primary"].addEventListener("click", () => {
  if (run.phase === "paused") togglePause();
  else if (run.phase === "over") start();
});
ui.home.addEventListener("click", () => {
  run = createRun();
  messageUntil = 0;
  syncUI();
  ui.start.focus({ preventScroll: true });
});

window.addEventListener("keydown", (event) => {
  const { code } = event;
  if (event.metaKey || event.ctrlKey || event.altKey) return;
  if (!Object.hasOwn(KEYS, code) && !["Enter", "Escape", "KeyR"].includes(code)) return;
  event.preventDefault();
  if (event.repeat) return;

  if (code === "Escape") togglePause();
  else if (code === "KeyR" && run.phase !== "ready") start();
  else if (code === "Enter" || code === "Space") {
    if (run.phase === "ready" || run.phase === "over") start();
    else if (run.phase === "paused") togglePause();
    else if (code === "Space") doAction("jump");
  } else if (KEYS[code]) doAction(KEYS[code]);
});

document.addEventListener("visibilitychange", () => {
  if (document.hidden && run.phase === "running") togglePause();
});

try {
  const stage = await createScene(ui.viewport);
  loaded = true;
  ui.start.disabled = false;
  text(ui["start-label"], "三道追逐");
  text(ui["load-note"], "空格或 Enter 开始");
  syncUI();
  let previous = performance.now();
  function frame(now) {
    const dt = Math.min(0.05, (now - previous) / 1000);
    previous = now;
    stepRun(run, dt);
    const flashing = run.hitFlash > 0;
    if (flashing && (!wasFlashing || hitKind !== run.lastHit) && run.phase === "running") {
      showNotice("鲸尾护盾挡住了！");
    }
    hitKind = run.lastHit;
    wasFlashing = flashing;
    stage.render(run, dt);
    syncUI();
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
} catch (error) {
  console.error(error);
  text(ui["start-label"], "场景加载失败");
  text(ui["load-note"], "请刷新页面重试。若仍无法打开，检查浏览器的图形加速。");
}
