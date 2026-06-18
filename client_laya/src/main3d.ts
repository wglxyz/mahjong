// Laya 3D spike: validate the code-first 3D pipeline (init, perspective camera,
// meshes, materials) before building the real 3D mahjong table.
// UnlitMaterial = no lights needed for this first pass.

const logEl = document.getElementById("log")!;
const log = (s: string) => { const d = document.createElement("div"); d.textContent = s; logEl.appendChild(d); };

async function main() {
  const t0 = performance.now();
  // anti-aliasing: WebGL MSAA context + render at device pixel ratio (capped)
  Laya.Config.isAntialias = true;
  Laya.Config.useRetinalCanvas = true;
  Laya.Config3D.pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
  await Laya.init(window.innerWidth, window.innerHeight);
  Laya.stage.scaleMode = "fixedauto";
  Laya.stage.bgColor = "#0b352a";
  log(`Laya init (3D present=${!!(window as any).Laya3D}): ${(performance.now() - t0).toFixed(0)}ms`);

  const scene = Laya.stage.addChild(new Laya.Scene3D()) as Laya.Scene3D;

  // perspective camera looking down at the table at a Mahjong-Soul-ish angle
  const camera = scene.addChild(new Laya.Camera(0, 0.1, 200)) as Laya.Camera;
  camera.transform.position = new Laya.Vector3(0, 11, 8);
  camera.transform.rotationEuler = new Laya.Vector3(-54, 0, 0);
  camera.clearFlag = Laya.CameraClearFlags.SolidColor;
  camera.clearColor = new Laya.Color(0.04, 0.22, 0.16, 1);
  camera.fieldOfView = 45;
  camera.msaa = true;          // per-camera multisample anti-aliasing

  // green felt table
  const ground = scene.addChild(new Laya.MeshSprite3D(Laya.PrimitiveMesh.createBox(20, 0.4, 14))) as Laya.MeshSprite3D;
  ground.transform.position = new Laya.Vector3(0, -0.2, 0);
  const gm = new Laya.UnlitMaterial(); gm.albedoColor = new Laya.Color(0.07, 0.42, 0.27, 1);
  ground.meshRenderer.material = gm;

  // a row of standing "tiles" (ivory boxes) at the near edge = your hand
  const ivory = new Laya.UnlitMaterial(); ivory.albedoColor = new Laya.Color(0.96, 0.93, 0.82, 1);
  const TW = 0.62, TH = 0.9, TD = 0.14;
  for (let i = 0; i < 13; i++) {
    const tile = scene.addChild(new Laya.MeshSprite3D(Laya.PrimitiveMesh.createBox(TW, TH, TD))) as Laya.MeshSprite3D;
    tile.transform.position = new Laya.Vector3((i - 6) * (TW + 0.05), TH / 2, 5.2);
    tile.meshRenderer.material = ivory;
  }
  // a few flat tiles in the center = discards
  for (let i = 0; i < 6; i++) {
    const d = scene.addChild(new Laya.MeshSprite3D(Laya.PrimitiveMesh.createBox(TW, TD, TH))) as Laya.MeshSprite3D;
    d.transform.position = new Laya.Vector3((i - 3) * (TW + 0.06), TD / 2, 1.2);
    d.meshRenderer.material = ivory;
  }

  log("3D scene built: camera + felt + standing hand + flat discards");
}

main().catch((e) => log("ERR " + (e?.message || e)));
