// Laya 3D mahjong table — step 1a: blue felt, high top-down camera, four hands
// (standing) + pinwheel discard ponds (flat), all ivory boxes for now. Tile face
// textures come in 1b once the camera/layout is confirmed.

const logEl = document.getElementById("log")!;
const log = (s: string) => { const d = document.createElement("div"); d.textContent = s; logEl.appendChild(d); };

// table geometry (world units)
const TW = 0.70, TH = 0.96, TT = 0.16;   // tile width / height(face) / thickness
const EDGE = 5.4;                          // distance of a hand row from center

let scene: Laya.Scene3D;
let standMesh: Laya.Mesh, flatMesh: Laya.Mesh;
let ivory: Laya.UnlitMaterial, ivoryBack: Laya.UnlitMaterial;

function tile(mat: Laya.UnlitMaterial, flat: boolean, x: number, z: number, rotY: number) {
  const sp = scene.addChild(new Laya.MeshSprite3D(flat ? flatMesh : standMesh)) as Laya.MeshSprite3D;
  sp.meshRenderer.sharedMaterial = mat;
  sp.transform.position = new Laya.Vector3(x, flat ? TT / 2 : TH / 2, z);
  if (rotY) sp.transform.rotationEuler = new Laya.Vector3(0, rotY, 0);
  return sp;
}

// a hand of `n` standing tiles centered along an edge; rel 0=you(near,+Z) 1=right 2=far 3=left
function hand(rel: number, n: number, mat: Laya.UnlitMaterial) {
  const span = (n - 1) * (TW + 0.04);
  for (let i = 0; i < n; i++) {
    const off = -span / 2 + i * (TW + 0.04);
    if (rel === 0) tile(mat, false, off, EDGE, 0);
    else if (rel === 2) tile(mat, false, -off, -EDGE, 180);
    else if (rel === 1) tile(mat, false, EDGE, -off, 90);
    else tile(mat, false, -EDGE, off, 90);
  }
}

// a discard pond: 6-per-row flat tiles in front of a player, growing toward them
function pond(rel: number, n: number) {
  const cols = 6, cw = TW + 0.03, rh = TH + 0.03, near = 1.7;
  for (let i = 0; i < n; i++) {
    const c = i % cols, r = Math.floor(i / cols);
    const lat = (c - (cols - 1) / 2) * cw;   // sideways
    const dep = near + r * rh;                // toward the player from center
    if (rel === 0) tile(ivory, true, lat, dep, 0);
    else if (rel === 2) tile(ivory, true, -lat, -dep, 0);
    else if (rel === 1) tile(ivory, true, dep, -lat, 90);
    else tile(ivory, true, -dep, lat, 90);
  }
}

async function main() {
  const t0 = performance.now();
  Laya.Config.isAntialias = true;
  Laya.Config.useRetinalCanvas = true;
  Laya.Config3D.pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
  await Laya.init(window.innerWidth, window.innerHeight);
  Laya.stage.scaleMode = "fixedauto";
  Laya.stage.bgColor = "#0a1d2e";
  log(`Laya init (3D=${!!(window as any).Laya3D}): ${(performance.now() - t0).toFixed(0)}ms`);

  scene = Laya.stage.addChild(new Laya.Scene3D()) as Laya.Scene3D;

  // high top-down camera (Mahjong-Soul-ish)
  const camera = scene.addChild(new Laya.Camera(0, 0.1, 200)) as Laya.Camera;
  camera.transform.position = new Laya.Vector3(0, 13, 8.2);
  camera.transform.rotationEuler = new Laya.Vector3(-60, 0, 0);
  camera.fieldOfView = 42;
  camera.clearFlag = Laya.CameraClearFlags.SolidColor;
  camera.clearColor = new Laya.Color(0.04, 0.11, 0.18, 1);
  camera.msaa = true;

  // meshes + materials (UnlitMaterial = no lights)
  standMesh = Laya.PrimitiveMesh.createBox(TW, TH, TT);
  flatMesh = Laya.PrimitiveMesh.createBox(TW, TT, TH);
  ivory = new Laya.UnlitMaterial(); ivory.albedoColor = new Laya.Color(0.95, 0.92, 0.81, 1);
  ivoryBack = new Laya.UnlitMaterial(); ivoryBack.albedoColor = new Laya.Color(0.88, 0.85, 0.74, 1);

  // blue felt table
  const felt = scene.addChild(new Laya.MeshSprite3D(Laya.PrimitiveMesh.createBox(14, 0.4, 14))) as Laya.MeshSprite3D;
  felt.transform.position = new Laya.Vector3(0, -0.2, 0);
  const feltMat = new Laya.UnlitMaterial(); feltMat.albedoColor = new Laya.Color(0.10, 0.22, 0.34, 1);
  felt.meshRenderer.sharedMaterial = feltMat;

  // four hands: you (face — ivory front) + 3 opponents (backs — slightly darker)
  hand(0, 13, ivory);
  hand(1, 13, ivoryBack);
  hand(2, 13, ivoryBack);
  hand(3, 13, ivoryBack);

  // four discard ponds (pinwheel)
  pond(0, 8); pond(1, 6); pond(2, 7); pond(3, 5);

  log("3D table 1a: blue felt + 4 standing hands + pinwheel ponds (ivory boxes)");
}

main().catch((e) => log("ERR " + (e?.message || e)));
