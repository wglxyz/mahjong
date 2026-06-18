// Laya 3D mahjong table — step 1b: textured tile faces.
// Tiles are ivory 3D boxes with a face-image quad on the visible side (front for
// your reclined hand, top for flat discards). Sample tiles for now; real data later.

const logEl = document.getElementById("log")!;
const log = (s: string) => { const d = document.createElement("div"); d.textContent = s; logEl.appendChild(d); };

const TW = 0.70, TH = 0.96, TT = 0.16, EDGE = 5.4, LEAN = 52;

// face-file mapping (same art as the 2D client)
const FACE: Record<string, string[]> = {
  m: ["", "Man1", "Man2", "Man3", "Man4", "Man5", "Man6", "Man7", "Man8", "Man9"],
  p: ["", "Pin1", "Pin2", "Pin3", "Pin4", "Pin5", "Pin6", "Pin7", "Pin8", "Pin9"],
  s: ["", "Sou1", "Sou2", "Sou3", "Sou4", "Sou5", "Sou6", "Sou7", "Sou8", "Sou9"],
  z: ["", "Ton", "Nan", "Shaa", "Pei", "Haku", "Hatsu", "Chun"],
};
const faceFile = (code: string) => (FACE[code[0]] || [])[+code.slice(1)] || "Front";
const url = (name: string) => `/laya/tiles/${name}.svg?v=lay340`;

// sample data (until real WS data in step 3)
const MY_HAND = ["m1", "m2", "m3", "p3", "p4", "p5", "s6", "s7", "s8", "z1", "z1", "z6", "z6"];
const PONDS = [
  ["m9", "p2", "z3", "s1", "z5", "p8", "m4", "s9"],
  ["z2", "p1", "s4", "m6", "z7", "p9"],
  ["s2", "m5", "z4", "p6", "s5", "z1", "m8"],
  ["p7", "z6", "s3", "m2", "z2"],
];

let scene: Laya.Scene3D;
let standMesh: Laya.Mesh, flatMesh: Laya.Mesh, quadMesh: Laya.Mesh;
let ivory: Laya.UnlitMaterial, ivoryBack: Laya.UnlitMaterial;
const matCache = new Map<string, Laya.UnlitMaterial>();

function faceMat(name: string): Laya.UnlitMaterial {
  let m = matCache.get(name);
  if (m) return m;
  m = new Laya.UnlitMaterial();
  const tex = Laya.loader.getRes(url(name)) as Laya.Texture;
  if (tex && tex.bitmap) m.albedoTexture = tex.bitmap;
  m.albedoColor = new Laya.Color(1, 1, 1, 1);
  m.renderMode = Laya.UnlitMaterial.RENDERMODE_TRANSPARENT;
  matCache.set(name, m);
  return m;
}

// a tile body + optional face quad on its visible side
function tile(bodyMat: Laya.UnlitMaterial, flat: boolean, x: number, y: number, z: number, rotX: number, rotY: number, faceCode?: string) {
  const sp = scene.addChild(new Laya.MeshSprite3D(flat ? flatMesh : standMesh)) as Laya.MeshSprite3D;
  sp.meshRenderer.sharedMaterial = bodyMat;
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
    if (rel === 0) tile(ivory, false, off, yLean, EDGE, -LEAN, 0, code);   // you: reclined, faces up
    else if (rel === 2) tile(ivoryBack, false, -off, TH / 2, -EDGE, 0, 180);
    else if (rel === 1) tile(ivoryBack, false, EDGE, TH / 2, -off, 0, 90);
    else tile(ivoryBack, false, -EDGE, TH / 2, off, 0, 90);
  }
}

function pond(rel: number, codes: string[]) {
  const cols = 6, cw = TW + 0.03, rh = TH + 0.03, near = 2.0;
  codes.forEach((code, i) => {
    const c = i % cols, r = Math.floor(i / cols);
    const lat = (c - (cols - 1) / 2) * cw;
    const dep = near + r * rh;
    const y = TT / 2;
    if (rel === 0) tile(ivory, true, lat, y, dep, 0, 0, code);
    else if (rel === 2) tile(ivory, true, -lat, y, -dep, 0, 0, code);
    else if (rel === 1) tile(ivory, true, dep, y, -lat, 0, 90, code);
    else tile(ivory, true, -dep, y, lat, 0, 90, code);
  });
}

async function main() {
  const t0 = performance.now();
  Laya.Config.isAntialias = true;
  Laya.Config.useRetinalCanvas = true;
  Laya.Config3D.pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
  await Laya.init(window.innerWidth, window.innerHeight);
  Laya.stage.scaleMode = "fixedauto";
  Laya.stage.bgColor = "#0a1d2e";

  // preload all tile face textures we use (+ Back) via the proven image loader
  const names = new Set<string>(["Front", "Back"]);
  [...MY_HAND, ...PONDS.flat()].forEach((c) => names.add(faceFile(c)));
  try { await Laya.loader.load([...names].map((n) => ({ url: url(n), type: Laya.Loader.IMAGE }))); log(`textures: ${names.size} (${(performance.now() - t0).toFixed(0)}ms)`); }
  catch (e) { log("texture load err: " + e); }

  scene = Laya.stage.addChild(new Laya.Scene3D()) as Laya.Scene3D;
  const camera = scene.addChild(new Laya.Camera(0, 0.1, 200)) as Laya.Camera;
  camera.transform.position = new Laya.Vector3(0, 8.6, 10);
  camera.transform.rotationEuler = new Laya.Vector3(-42, 0, 0);
  camera.fieldOfView = 50;
  camera.clearFlag = Laya.CameraClearFlags.SolidColor;
  camera.clearColor = new Laya.Color(0.04, 0.11, 0.18, 1);
  camera.msaa = true;

  standMesh = Laya.PrimitiveMesh.createBox(TW, TH, TT);
  flatMesh = Laya.PrimitiveMesh.createBox(TW, TT, TH);
  quadMesh = Laya.PrimitiveMesh.createQuad(TW, TH);
  ivory = new Laya.UnlitMaterial(); ivory.albedoColor = new Laya.Color(0.95, 0.92, 0.81, 1);
  ivoryBack = new Laya.UnlitMaterial(); ivoryBack.albedoColor = new Laya.Color(0.88, 0.85, 0.74, 1);

  const felt = scene.addChild(new Laya.MeshSprite3D(Laya.PrimitiveMesh.createBox(14, 0.4, 14))) as Laya.MeshSprite3D;
  felt.transform.position = new Laya.Vector3(0, -0.2, 0);
  const feltMat = new Laya.UnlitMaterial(); feltMat.albedoColor = new Laya.Color(0.10, 0.22, 0.34, 1);
  felt.meshRenderer.sharedMaterial = feltMat;

  hand(0, MY_HAND);
  hand(1, 13); hand(2, 13); hand(3, 13);
  PONDS.forEach((codes, rel) => pond(rel, codes));

  log("3D table 1b: textured faces (your hand + ponds), opponents ivory");
}

main().catch((e) => log("ERR " + (e?.message || e)));
