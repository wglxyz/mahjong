// Laya 3D mahjong table. Tiles are rounded-corner boxes (custom mesh): cream
// face panel + symbol over an amber body. Sample tiles for now; real data later.

const logEl = document.getElementById("log")!;
const log = (s: string) => { const d = document.createElement("div"); d.textContent = s; logEl.appendChild(d); };

const DEBUG_SINGLE = false;

// real-tile proportions ~ width:height:depth = 3:4:2; rounded corners
const TW = 0.70, TH = 0.93, TT = 0.44, R = 0.07, SEG = 4, EDGE = 5.0, LEAN = 52;

const FACE: Record<string, string[]> = {
  m: ["", "Man1", "Man2", "Man3", "Man4", "Man5", "Man6", "Man7", "Man8", "Man9"],
  p: ["", "Pin1", "Pin2", "Pin3", "Pin4", "Pin5", "Pin6", "Pin7", "Pin8", "Pin9"],
  s: ["", "Sou1", "Sou2", "Sou3", "Sou4", "Sou5", "Sou6", "Sou7", "Sou8", "Sou9"],
  z: ["", "Ton", "Nan", "Shaa", "Pei", "Haku", "Hatsu", "Chun"],
};
const faceFile = (code: string) => (FACE[code[0]] || [])[+code.slice(1)] || "Front";
const url = (name: string) => `/laya/tiles/${name}.svg?v=lay340`;

const MY_HAND = ["m1", "m2", "m3", "p3", "p4", "p5", "s6", "s7", "s8", "z1", "z1", "z6", "z6"];
const PONDS = [
  ["m9", "p2", "z3", "s1", "z5", "p8", "m4", "s9"],
  ["z2", "p1", "s4", "m6", "z7", "p9"],
  ["s2", "m5", "z4", "p6", "s5", "z1", "m8"],
  ["p7", "z6", "s3", "m2", "z2"],
];

let scene: Laya.Scene3D;
let tileMesh: Laya.Mesh, panelMesh: Laya.Mesh, symMesh: Laya.Mesh;
let bodyMat: Laya.BlinnPhongMaterial, frontMat: Laya.UnlitMaterial;
const faceCache = new Map<string, Laya.UnlitMaterial>();

// rounded-rectangle prism (face in XY at ±depth/2, front normal +Z), built from
// raw vertices via the same internal createBox/createQuad uses.
function roundedTileMesh(w: number, h: number, d: number, r: number, seg: number): Laya.Mesh {
  const hw = w / 2, hh = h / 2, hd = d / 2;
  const corners: [number, number, number][] = [[hw - r, hh - r, 0], [-(hw - r), hh - r, 90], [-(hw - r), -(hh - r), 180], [hw - r, -(hh - r), 270]];
  const peri: [number, number][] = [];
  for (const [cx, cy, a0] of corners)
    for (let i = 0; i <= seg; i++) { const a = (a0 + i * (90 / seg)) * Math.PI / 180; peri.push([cx + r * Math.cos(a), cy + r * Math.sin(a)]); }
  const P = peri.length;
  const v: number[] = [], idx: number[] = []; let n = 0;
  const add = (x: number, y: number, z: number, nx: number, ny: number, nz: number, u: number, vv: number) => { v.push(x, y, z, nx, ny, nz, u, vv, 1, 0, 0, 1); return n++; };

  const fc = add(0, 0, hd, 0, 0, 1, 0.5, 0.5);
  const fr: number[] = peri.map(([x, y]) => add(x, y, hd, 0, 0, 1, x / w + 0.5, 0.5 - y / h));
  for (let i = 0; i < P; i++) idx.push(fc, fr[i], fr[(i + 1) % P]);

  const bc = add(0, 0, -hd, 0, 0, -1, 0.5, 0.5);
  const br: number[] = peri.map(([x, y]) => add(x, y, -hd, 0, 0, -1, x / w + 0.5, 0.5 - y / h));
  for (let i = 0; i < P; i++) idx.push(bc, br[(i + 1) % P], br[i]);

  for (let i = 0; i < P; i++) {
    const j = (i + 1) % P, [x0, y0] = peri[i], [x1, y1] = peri[j];
    const mx = (x0 + x1) / 2, my = (y0 + y1) / 2, ml = Math.hypot(mx, my) || 1, nx = mx / ml, ny = my / ml;
    const a = add(x0, y0, hd, nx, ny, 0, 0, 0), b = add(x1, y1, hd, nx, ny, 0, 1, 0);
    const c = add(x0, y0, -hd, nx, ny, 0, 0, 1), e = add(x1, y1, -hd, nx, ny, 0, 1, 1);
    idx.push(a, c, b, b, c, e);
  }
  const decl = (Laya as any).VertexMesh.getVertexDeclaration("POSITION,NORMAL,UV,TANGENT");
  return (Laya.PrimitiveMesh as any)._createMesh(decl, new Float32Array(v), new Uint16Array(idx));
}

function faceMat(name: string): Laya.UnlitMaterial {
  let m = faceCache.get(name);
  if (m) return m;
  m = new Laya.UnlitMaterial();
  const tex = Laya.loader.getRes(url(name)) as Laya.Texture;
  if (tex && tex.bitmap) m.albedoTexture = tex.bitmap;
  m.albedoColor = new Laya.Color(1, 1, 1, 1);
  m.renderMode = Laya.UnlitMaterial.RENDERMODE_TRANSPARENT;
  faceCache.set(name, m);
  return m;
}

// one tile: rounded amber body + optional cream face panel & symbol on the front (+Z local)
function tile(x: number, y: number, z: number, rotX: number, rotY: number, faceCode?: string) {
  const sp = scene.addChild(new Laya.MeshSprite3D(tileMesh)) as Laya.MeshSprite3D;
  sp.meshRenderer.sharedMaterial = bodyMat;
  sp.transform.position = new Laya.Vector3(x, y, z);
  sp.transform.rotationEuler = new Laya.Vector3(rotX, rotY, 0);
  if (faceCode) {
    const panel = new Laya.MeshSprite3D(panelMesh) as Laya.MeshSprite3D;
    panel.meshRenderer.sharedMaterial = frontMat;
    panel.transform.localPosition = new Laya.Vector3(0, 0, TT / 2 + 0.008);
    const sym = new Laya.MeshSprite3D(symMesh) as Laya.MeshSprite3D;
    sym.meshRenderer.sharedMaterial = faceMat(faceFile(faceCode));
    sym.transform.localPosition = new Laya.Vector3(0, 0, TT / 2 + 0.012);
    sp.addChild(panel); sp.addChild(sym);
  }
  return sp;
}

function hand(rel: number, codes: string[] | number) {
  const n = typeof codes === "number" ? codes : codes.length;
  const span = (n - 1) * (TW + 0.04);
  const yLean = TH / 2 * Math.cos(LEAN * Math.PI / 180) + 0.05;
  for (let i = 0; i < n; i++) {
    const off = -span / 2 + i * (TW + 0.04);
    const code = typeof codes === "number" ? undefined : codes[i];
    if (rel === 0) tile(off, yLean, EDGE, -LEAN, 0, code);    // you: reclined, face up toward camera
    else if (rel === 2) tile(-off, TH / 2, -EDGE, 0, 0);      // opponents: upright amber (backs)
    else if (rel === 1) tile(EDGE, TH / 2, -off, 0, 90);
    else tile(-EDGE, TH / 2, off, 0, 90);
  }
}

function pond(rel: number, codes: string[]) {
  const cols = 6, cw = TW + 0.03, rh = TH + 0.03, near = 2.0;
  codes.forEach((code, i) => {
    const c = i % cols, r = Math.floor(i / cols);
    const lat = (c - (cols - 1) / 2) * cw, dep = near + r * rh, y = TT / 2;
    if (rel === 0) tile(lat, y, dep, -90, 0, code);          // lying flat, face up
    else if (rel === 2) tile(-lat, y, -dep, -90, 0, code);
    else if (rel === 1) tile(dep, y, -lat, -90, 90, code);
    else tile(-dep, y, lat, -90, 90, code);
  });
}

function buildSingle() {
  const y = TH / 2;
  tile(-0.9, y, 0, 0, 0, "m5");
  tile(0, y, 0, 0, 0);
  tile(0.9, y, 0, 0, 0, "z7");
}

function overlay() {
  const cx = Laya.stage.width / 2, cy = Laya.stage.height / 2;
  const lab = (t: string, x: number, y: number, size: number, color: string) => {
    const tx = new Laya.Text(); tx.text = t; tx.fontSize = size; tx.color = color; tx.bold = true;
    tx.align = "center"; tx.width = 160; tx.pos(x - 80, y); Laya.stage.addChild(tx);
  };
  lab("東 1 局", cx, cy - 12, 22, "#e7c46a");
  lab("25000", cx, cy + 70, 16, "#f2efe6");
  lab("25000", cx, cy - 78, 16, "#f2efe6");
  lab("25000", cx + 90, cy - 6, 16, "#f2efe6");
  lab("25000", cx - 90, cy - 6, 16, "#f2efe6");
}

async function main() {
  const t0 = performance.now();
  Laya.Config.isAntialias = true;
  Laya.Config.useRetinalCanvas = true;
  Laya.Config3D.pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
  await Laya.init(window.innerWidth, window.innerHeight);
  Laya.stage.scaleMode = "fixedauto";
  Laya.stage.bgColor = "#0a1d2e";

  const names = new Set<string>(["Front", "Back"]);
  [...MY_HAND, ...PONDS.flat(), "m5", "z7"].forEach((c) => names.add(faceFile(c)));
  try { await Laya.loader.load([...names].map((n) => ({ url: url(n), type: Laya.Loader.IMAGE }))); log(`textures: ${names.size} (${(performance.now() - t0).toFixed(0)}ms)`); }
  catch (e) { log("texture load err: " + e); }

  scene = Laya.stage.addChild(new Laya.Scene3D()) as Laya.Scene3D;
  scene.ambientMode = Laya.AmbientMode.SolidColor;
  scene.ambientColor = new Laya.Color(0.78, 0.78, 0.78, 1);
  scene.ambientIntensity = 1;
  const lightNode = scene.addChild(new Laya.Sprite3D()) as Laya.Sprite3D;
  const dl = lightNode.addComponent(Laya.DirectionLightCom);
  dl.color = new Laya.Color(1, 1, 1, 1); dl.intensity = 0.5;
  lightNode.transform.rotationEuler = new Laya.Vector3(-60, 20, 0);

  const camera = scene.addChild(new Laya.Camera(0, 0.1, 200)) as Laya.Camera;
  camera.clearFlag = Laya.CameraClearFlags.SolidColor;
  camera.clearColor = new Laya.Color(0.04, 0.11, 0.18, 1);
  camera.msaa = true;
  if (DEBUG_SINGLE) { camera.transform.position = new Laya.Vector3(0, 1.7, 3.4); camera.transform.rotationEuler = new Laya.Vector3(-20, 0, 0); camera.fieldOfView = 45; }
  else { camera.transform.position = new Laya.Vector3(0, 7.8, 9.2); camera.transform.rotationEuler = new Laya.Vector3(-43, 0, 0); camera.fieldOfView = 52; }

  tileMesh = roundedTileMesh(TW, TH, TT, R, SEG);
  panelMesh = Laya.PrimitiveMesh.createQuad(TW * 0.9, TH * 0.92);
  symMesh = Laya.PrimitiveMesh.createQuad(TW * 0.76, TH * 0.76);
  bodyMat = new Laya.BlinnPhongMaterial(); bodyMat.albedoColor = new Laya.Color(0.93, 0.85, 0.62, 1);
  bodyMat.cull = Laya.RenderState.CULL_NONE;   // double-sided: tolerant of mesh winding
  frontMat = new Laya.UnlitMaterial();
  const frontTex = Laya.loader.getRes(url("Front")) as Laya.Texture;
  if (frontTex && frontTex.bitmap) frontMat.albedoTexture = frontTex.bitmap;
  frontMat.albedoColor = new Laya.Color(1, 1, 1, 1);
  frontMat.renderMode = Laya.UnlitMaterial.RENDERMODE_TRANSPARENT;

  if (DEBUG_SINGLE) { buildSingle(); log("single-tile view"); return; }

  const felt = scene.addChild(new Laya.MeshSprite3D(Laya.PrimitiveMesh.createBox(12.6, 0.4, 12.6))) as Laya.MeshSprite3D;
  felt.transform.position = new Laya.Vector3(0, -0.2, 0);
  const feltMat = new Laya.BlinnPhongMaterial(); feltMat.albedoColor = new Laya.Color(0.10, 0.22, 0.34, 1);
  felt.meshRenderer.sharedMaterial = feltMat;

  const cube = scene.addChild(new Laya.MeshSprite3D(Laya.PrimitiveMesh.createBox(2.0, 0.5, 2.0))) as Laya.MeshSprite3D;
  cube.transform.position = new Laya.Vector3(0, 0.25, 0);
  const cubeMat = new Laya.BlinnPhongMaterial(); cubeMat.albedoColor = new Laya.Color(0.05, 0.10, 0.15, 1);
  cube.meshRenderer.sharedMaterial = cubeMat;

  hand(0, MY_HAND); hand(1, 13); hand(2, 13); hand(3, 13);
  PONDS.forEach((codes, rel) => pond(rel, codes));
  overlay();
  log("3D table: rounded tiles (amber body + cream face)");
}

main().catch((e) => log("ERR " + (e?.message || e)));
