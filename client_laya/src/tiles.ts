// Tile asset handling: code → face-file mapping, preload, and sprite factory.
// Tiles render as the Front body with the face SVG drawn on top.
import type { TileView } from "./protocol";

const FACE: Record<string, string[]> = {
  m: ["", "Man1", "Man2", "Man3", "Man4", "Man5", "Man6", "Man7", "Man8", "Man9"],
  p: ["", "Pin1", "Pin2", "Pin3", "Pin4", "Pin5", "Pin6", "Pin7", "Pin8", "Pin9"],
  s: ["", "Sou1", "Sou2", "Sou3", "Sou4", "Sou5", "Sou6", "Sou7", "Sou8", "Sou9"],
  z: ["", "Ton", "Nan", "Shaa", "Pei", "Haku", "Hatsu", "Chun"],
};
const RED_FACE: Record<string, string> = { m: "Man5-Dora", p: "Pin5-Dora", s: "Sou5-Dora" };
const TILE_RATIO = 4 / 3; // height / width (SVG viewBox 300x400)

const url = (name: string) => `/laya/tiles/${name}.svg`;

export function faceFile(t: TileView): string {
  const suit = t.code[0];
  const rank = +t.code.slice(1);
  if (t.red && RED_FACE[suit]) return RED_FACE[suit];
  return (FACE[suit] || [])[rank] || "Front";
}

function allTileNames(): string[] {
  const names = new Set<string>(["Front", "Back"]);
  for (const suit of ["m", "p", "s"]) for (let r = 1; r <= 9; r++) names.add(FACE[suit][r]);
  for (const z of FACE.z) if (z) names.add(z);
  for (const k in RED_FACE) names.add(RED_FACE[k]);
  return [...names];
}

// Force type=image: Laya's loader has no .svg parser, but the image loader uses
// an <img>, which natively rasterizes SVG into a texture.
export function preloadTiles(): Promise<any> {
  return Laya.loader.load(allTileNames().map((n) => ({ url: url(n), type: Laya.Loader.IMAGE })));
}

// Fake 3D using the Front silhouette (keeps rounded corners): a soft drop shadow
// + a darker "lip" offset down for thickness, then the body, then the face.
export function makeTile(t: TileView, w: number): Laya.Sprite {
  const h = Math.round(w * TILE_RATIO);
  const lip = Math.max(2, Math.round(w * 0.07));
  const sp = new Laya.Sprite();
  const g = sp.graphics;
  const front = Laya.loader.getRes(url("Front"));
  if (front) {
    g.drawTexture(front, Math.round(w * 0.04), lip + 2, w, h, null, 0.3, "#000000");  // drop shadow
    g.drawTexture(front, 0, lip, w, h, null, 1, "#b3a784");                            // thickness lip
    g.drawTexture(front, 0, 0, w, h);                                                  // body
  }
  const face = Laya.loader.getRes(url(faceFile(t)));
  if (face) g.drawTexture(face, 0, 0, w, h);
  sp.size(w, h + lip + 2);
  return sp;
}

export function makeBack(w: number): Laya.Sprite {
  const h = Math.round(w * TILE_RATIO);
  const lip = Math.max(2, Math.round(w * 0.07));
  const sp = new Laya.Sprite();
  const g = sp.graphics;
  const back = Laya.loader.getRes(url("Back"));
  if (back) {
    g.drawTexture(back, Math.round(w * 0.04), lip + 2, w, h, null, 0.3, "#000000");
    g.drawTexture(back, 0, lip, w, h, null, 1, "#0c3a2c");
    g.drawTexture(back, 0, 0, w, h);
  }
  sp.size(w, h + lip + 2);
  return sp;
}

export const tileSize = (w: number) => ({ w, h: Math.round(w * TILE_RATIO) });
