// Entry: init Laya, preload tiles, wire net → model → table.
// `Laya` is a global from the vendored engine scripts; types from types/LayaAir.d.ts.
import { Net } from "./net";
import { GameModel } from "./state";
import { preloadTiles } from "./tiles";
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
    case "decision": {
      pending = m.actions;
      const hasDiscard = m.actions.some((a) => a.kind === "discard");
      if (hasDiscard) {
        scheduleRender(); // wait for the player to click a tile
      } else {
        // chunk 1: no action-button UI yet → auto-pass response windows so play continues
        const pass = m.actions.find((a) => a.kind === "pass") || m.actions[0];
        net.decide(pass.id); pending = null;
      }
      break;
    }
    case "hand_ended": log(`hand_ended ${m.result}${m.winner != null ? " winner=" + m.winner : ""}`); break;
    case "match_ended": log("match_ended " + JSON.stringify(m.final_points)); break;
    case "error": log("ERROR " + m.error); break;
  }
}

async function main() {
  Laya.Config.useRetinalCanvas = true;  // sharp tiles on HiDPI / retina screens
  await Laya.init(DESIGN_W, DESIGN_H);
  Laya.stage.scaleMode = "showall";
  Laya.stage.alignH = "center";
  Laya.stage.alignV = "middle";
  Laya.stage.bgColor = "#0b352a";
  log("Laya inited");

  try { await preloadTiles(); log("tiles preloaded"); }
  catch (e) { log("tile preload error: " + e); }

  table = new TableView(Laya.stage as unknown as Laya.Sprite);
  table.onDiscard = (t) => {
    if (!pending) return;
    const a = pending.find((x) => x.kind === "discard" && (x.tiles || []).some((tt) => tt.id === t.id));
    if (a) { net.decide(a.id); pending = null; table.render(model, pending); }
  };

  net.onStatus = (s) => log(s);
  net.onMessage = handle;
  net.connect();
}

main();
