// Laya 3D mahjong table — lighting + opponent backs + walls + framing + center text.
// Sample tiles for now; real WS data is a later step.

const logEl = document.getElementById("log")!;
const log = (s: string) => { const d = document.createElement("div"); d.textContent = s; logEl.appendChild(d); };

const TW = 0.70, TH = 0.96, TT = 0.18, EDGE = 5.0, WALL = 5.85, LEAN = 52;

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
let standMesh: Laya.Mesh, flatMesh: Laya.Mesh, quadMesh: Laya.Mesh;
let bodyMat: Laya.BlinnPhongMaterial, backMat: Laya.BlinnPhongMaterial;
const faceCache = new Map<string, Laya.UnlitMaterial>();

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

function tile(mat: Laya.BlinnPhongMaterial, flat: boolean, x: number, y: number, z: number, rotX: number, rotY: number, faceCode?: string) {
  const sp = scene.addChild(new Laya.MeshSprite3D(flat ? flatMesh : standMesh)) as Laya.MeshSprite3D;
  sp.meshRenderer.sharedMaterial = mat;
  sp.transform.position = new Laya.Vector3(x, y, z);
  if (rotX || rotY) sp.transform.rotationEuler = new Laya.Vector3(rotX, rotY, 0);
  if (faceCode) {
    const q = new Laya.MeshSprite3D(quadMesh) as Laya.MeshSprite3D;
    q.meshRenderer.sharedMaterial = faceMat(faceFile(faceCode));
    if (flat) { q.transform.localRotationEuler = new Laya.Vector3(-90, 0, 0); q.transform.localPosition = new Laya.Vector3(0, TT / 2 + 0.01, 0); }
    else { q.transform.localPosition = new Laya.Vector3(0, 0, TT / 2 + 0.01); }
    sp.addChild(q);
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
    if (rel === 0) tile(bodyMat, false, off, yLean, EDGE, -LEAN, 0, code);  // you: reclined faces
    else if (rel === 2) tile(backMat, false, -off, TH / 2, -EDGE, 0, 0);     // opponents: back-textured box
    else if (rel === 1) tile(backMat, false, EDGE, TH / 2, -off, 0, 90);
    else tile(backMat, false, -EDGE, TH / 2, off, 0, 90);
  }
}

function pond(rel: number, codes: string[]) {
  const cols = 6, cw = TW + 0.03, rh = TH + 0.03, near = 2.0;
  codes.forEach((code, i) => {
    const c = i % cols, r = Math.floor(i / cols);
    const lat = (c - (cols - 1) / 2) * cw, dep = near + r * rh, y = TT / 2;
    if (rel === 0) tile(bodyMat, true, lat, y, dep, 0, 0, code);
    else if (rel === 2) tile(bodyMat, true, -lat, y, -dep, 0, 0, code);
    else if (rel === 1) tile(bodyMat, true, dep, y, -lat, 0, 90, code);
    else tile(bodyMat, true, -dep, y, lat, 0, 90, code);
  });
}

// perimeter wall: a 2-high ridge of back-tiles along each edge
function walls() {
  const count = 17, step = TW + 0.02, start = -(count - 1) / 2 * step;
  for (let i = 0; i < count; i++) {
    const o = start + i * step;
    for (let layer = 0; layer < 2; layer++) {
      const y = TT / 2 + layer * TT;
      tile(bodyMat, true, o, y, WALL, 0, 0);     // walls are ivory (tile bodies seen from outside)
      tile(bodyMat, true, -o, y, -WALL, 0, 0);
      tile(bodyMat, true, WALL, y, o, 0, 90);
      tile(bodyMat, true, -WALL, y, -o, 0, 90);
    }
  }
}

function overlay() {
  const cx = Laya.stage.width / 2, cy = Laya.stage.height / 2;
  const lab = (t: string, x: number, y: number, size: number, color: string) => {
    const tx = new Laya.Text(); tx.text = t; tx.fontSize = size; tx.color = color; tx.bold = true;
    tx.align = "center"; tx.width = 160; tx.pos(x - 80, y); Laya.stage.addChild(tx);
  };
  lab("東 1 局", cx, cy - 12, 22, "#e7c46a");
  lab("25000", cx, cy + 70, 16, "#f2efe6");   // you (bottom)
  lab("25000", cx, cy - 78, 16, "#f2efe6");   // far (top)
  lab("25000", cx + 90, cy - 6, 16, "#f2efe6"); // right
  lab("25000", cx - 90, cy - 6, 16, "#f2efe6"); // left
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
  [...MY_HAND, ...PONDS.flat()].forEach((c) => names.add(faceFile(c)));
  try { await Laya.loader.load([...names].map((n) => ({ url: url(n), type: Laya.Loader.IMAGE }))); log(`textures: ${names.size} (${(performance.now() - t0).toFixed(0)}ms)`); }
  catch (e) { log("texture load err: " + e); }

  scene = Laya.stage.addChild(new Laya.Scene3D()) as Laya.Scene3D;
  // generous ambient so lit materials can never go black, + one directional light for sheen
  scene.ambientMode = Laya.AmbientMode.SolidColor;
  scene.ambientColor = new Laya.Color(0.62, 0.63, 0.66, 1);
  scene.ambientIntensity = 1;
  const lightNode = scene.addChild(new Laya.Sprite3D()) as Laya.Sprite3D;
  const dl = lightNode.addComponent(Laya.DirectionLightCom);
  dl.color = new Laya.Color(1, 0.97, 0.9, 1); dl.intensity = 1.1;
  lightNode.transform.rotationEuler = new Laya.Vector3(-55, 25, 0);

  const camera = scene.addChild(new Laya.Camera(0, 0.1, 200)) as Laya.Camera;
  camera.transform.position = new Laya.Vector3(0, 7.8, 9.2);
  camera.transform.rotationEuler = new Laya.Vector3(-43, 0, 0);
  camera.fieldOfView = 52;
  camera.clearFlag = Laya.CameraClearFlags.SolidColor;
  camera.clearColor = new Laya.Color(0.04, 0.11, 0.18, 1);
  camera.msaa = true;

  standMesh = Laya.PrimitiveMesh.createBox(TW, TH, TT);
  flatMesh = Laya.PrimitiveMesh.createBox(TW, TT, TH);
  quadMesh = Laya.PrimitiveMesh.createQuad(TW * 0.84, TH * 0.84);   // smaller → ivory border shows (H)
  bodyMat = new Laya.BlinnPhongMaterial(); bodyMat.albedoColor = new Laya.Color(0.96, 0.93, 0.82, 1);
  // opponent backs: teal solid (the FluffyStuff Back.svg is a red back — too loud);
  backMat = new Laya.BlinnPhongMaterial(); backMat.albedoColor = new Laya.Color(0.17, 0.45, 0.42, 1);

  const felt = scene.addChild(new Laya.MeshSprite3D(Laya.PrimitiveMesh.createBox(12.6, 0.4, 12.6))) as Laya.MeshSprite3D;
  felt.transform.position = new Laya.Vector3(0, -0.2, 0);
  const feltMat = new Laya.BlinnPhongMaterial(); feltMat.albedoColor = new Laya.Color(0.10, 0.22, 0.34, 1);
  felt.meshRenderer.sharedMaterial = feltMat;

  const cube = scene.addChild(new Laya.MeshSprite3D(Laya.PrimitiveMesh.createBox(2.0, 0.5, 2.0))) as Laya.MeshSprite3D;
  cube.transform.position = new Laya.Vector3(0, 0.25, 0);
  const cubeMat = new Laya.BlinnPhongMaterial(); cubeMat.albedoColor = new Laya.Color(0.05, 0.10, 0.15, 1);
  cube.meshRenderer.sharedMaterial = cubeMat;

  walls();
  hand(0, MY_HAND); hand(1, 13); hand(2, 13); hand(3, 13);
  PONDS.forEach((codes, rel) => pond(rel, codes));
  overlay();

  log("3D table: lighting + backs + walls + framing + center text");
}

main().catch((e) => log("ERR " + (e?.message || e)));
