// Laya code-first demo (no IDE): init engine, render real tile textures, connect WS.
// `Laya` is a global from /laya/libs/laya.core.js; types come from types/LayaAir.d.ts.

const logEl = document.getElementById("log")!;
function log(s: string) {
  const d = document.createElement("div");
  d.className = "row";
  d.textContent = s;
  logEl.appendChild(d);
  logEl.scrollTop = logEl.scrollHeight;
}

const TILES = [
  "Front", "Back", "Man1", "Man5", "Man5-Dora", "Man9",
  "Pin1", "Pin5", "Sou5", "Sou9", "Ton", "Nan", "Shaa", "Pei", "Haku", "Hatsu", "Chun",
];
const url = (n: string) => `/laya/tiles/${n}.svg`;

async function main() {
  await Laya.init(window.innerWidth, window.innerHeight);
  Laya.stage.bgColor = "#0b352a";
  log("Laya engine inited (WebGL)");

  // title
  const title = new Laya.Text();
  title.text = "Laya demo · 牌面渲染 + WebSocket";
  title.color = "#e7c46a";
  title.fontSize = 26;
  title.bold = true;
  title.pos(40, 50);
  Laya.stage.addChild(title);

  // load real tile SVGs (de-risks the asset pipeline under WebGL)
  try {
    await Laya.loader.load(TILES.map(url));
    log("tile assets loaded: " + TILES.length);
  } catch (e) {
    log("asset load error: " + e);
  }

  // draw each tile as Front body + face overlay, in a row
  const TW = 64, TH = 86, gap = 10, x0 = 40, y0 = 110;
  const front = Laya.loader.getRes(url("Front"));
  TILES.forEach((name, i) => {
    const sp = new Laya.Sprite();
    if (front) sp.graphics.drawTexture(front, 0, 0, TW, TH);
    const face = Laya.loader.getRes(url(name));
    if (face) sp.graphics.drawTexture(face, 0, 0, TW, TH);
    sp.pos(x0 + i * (TW + gap), y0);
    Laya.stage.addChild(sp);
  });
  log("rendered " + TILES.length + " tiles");

  connectWS();
}

function connectWS() {
  const wsUrl = (location.protocol === "https:" ? "wss:" : "ws:") + "//" + location.host + "/";
  log("connecting " + wsUrl);
  const ws = new WebSocket(wsUrl);
  ws.onopen = () => { log("ws open"); setTimeout(() => ws.send(JSON.stringify({ type: "request_snapshot" })), 300); };
  ws.onclose = (e) => log("ws close " + e.code);
  ws.onerror = () => log("ws error");
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data as string);
    if (m.type === "welcome") log(`welcome: seat=${m.your_seat} ruleset=${m.ruleset}`);
    else if (m.type === "snapshot") log(`snapshot: ${m.round_wind}-${m.hand_number} wall=${m.wall_count} dealer=${m.dealer}`);
    else if (m.type === "decision") {
      log("decision: " + m.actions.map((a: any) => a.kind).join(","));
      ws.send(JSON.stringify({ type: "decide", action_id: m.actions[0].id }));  // auto-play for demo
    } else if (m.type === "hand_ended") log("hand_ended: " + m.result);
    else if (m.type === "match_ended") log("match_ended");
  };
}

main();
