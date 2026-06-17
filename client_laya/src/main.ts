// Entry: init Laya, preload tiles, wire net → model → table.
// `Laya` is a global from the vendored engine scripts; types from types/LayaAir.d.ts.
import { Net } from "./net";
import { GameModel } from "./state";
import { preloadTiles, ASSET_VER } from "./tiles";
import { TableView, DESIGN_W, DESIGN_H } from "./table";
import type { ActionView, ServerMsg } from "./protocol";

const logEl = document.getElementById("log")!;
function log(s: string) {
  const d = document.createElement("div"); d.className = "row"; d.textContent = s;
  logEl.appendChild(d); logEl.scrollTop = logEl.scrollHeight;
  while (logEl.children.length > 200) logEl.removeChild(logEl.firstChild!);
}

const model = new GameModel();
let pending: ActionView[] | null = null;
let table: TableView;
const net = new Net();

// coalesce event bursts (AI turns) into one repaint per frame
let dirty = false;
function scheduleRender() { if (dirty) return; dirty = true; requestAnimationFrame(() => { dirty = false; table.render(model, pending); }); }

function handle(m: ServerMsg) {
  switch (m.type) {
    case "welcome":
      model.yourSeat = m.your_seat; model.seatNames = m.seats; model.ruleset = m.ruleset;
      log(`welcome seat=${m.your_seat} ${m.ruleset}`); break;
    case "snapshot": model.snap = m; scheduleRender(); break;
    case "event": model.applyEvent(m.event); scheduleRender(); break;
    case "decision":
      pending = m.actions;   // discards via hand click, others via the action buttons
      scheduleRender();
      break;
    case "hand_ended": log(`hand_ended ${m.result}${m.winner != null ? " winner=" + m.winner : ""}`); break;
    case "match_ended": log("match_ended " + JSON.stringify(m.final_points)); break;
    case "error": log("ERROR " + m.error); break;
  }
}

const boot = document.getElementById("boot")!;
const bootFill = document.getElementById("bootFill")!;
const bootPct = document.getElementById("bootPct")!;
function setBoot(p: number) { const pct = Math.round(p * 100); bootFill.style.width = pct + "%"; bootPct.textContent = pct + "%"; }
function hideBoot() { boot.classList.add("hide"); setTimeout(() => (boot.style.display = "none"), 400); }

async function main() {
  const t0 = performance.now();
  // warm cache → the pack is already on disk; skip the bar UI for an instant entry
  const warm = (() => { try { return localStorage.getItem("laya_pack_ver") === ASSET_VER; } catch { return false; } })();
  if (warm) boot.style.display = "none";

  Laya.Config.useRetinalCanvas = true;  // sharp tiles on HiDPI / retina screens
  await Laya.init(DESIGN_W, DESIGN_H);
  Laya.stage.scaleMode = "showall";
  Laya.stage.alignH = "center";
  Laya.stage.alignV = "middle";
  Laya.stage.bgColor = "#0b352a";
  const tInit = performance.now();
  log(`Laya init: ${(tInit - t0).toFixed(0)}ms`);

  try { await preloadTiles((p) => setBoot(p)); log(`tiles preloaded: ${(performance.now() - tInit).toFixed(0)}ms`); }
  catch (e) { log("tile preload error: " + e); }
  try { localStorage.setItem("laya_pack_ver", ASSET_VER); } catch {}
  if (!warm) hideBoot();

  table = new TableView(Laya.stage as unknown as Laya.Sprite);
  table.onDecide = (id) => { net.decide(id); pending = null; table.render(model, pending); };

  net.onStatus = (s) => log(s);
  net.onMessage = handle;
  net.connect();
}

main();
