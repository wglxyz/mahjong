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

// ?v lets tiles be cached immutably yet busted by bumping the version
export const ASSET_VER = "lay340";
const url = (name: string) => `/laya/tiles/${name}.svg?v=${ASSET_VER}`;

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
// an <img>, which natively rasterizes SVG into a texture. onProgress drives the
// boot bar (0..1).
export function preloadTiles(onProgress?: (p: number) => void): Promise<any> {
  const items = allTileNames().map((n) => ({ url: url(n), type: Laya.Loader.IMAGE }));
  return Laya.loader.load(items, undefined, onProgress ? ((p: number) => onProgress(p)) as any : undefined);
}

// Fake 2.5D like Mahjong Soul: a visible ivory bottom "side" (the tile's depth)
// + a soft drop shadow under it, then the top body, then the face. Using the
// Front silhouette for the side keeps the rounded corners consistent.
// sideOf() is the extra height the depth adds — layout must leave room for it.
export const sideOf = (w: number) => Math.max(4, Math.round(w * TILE_RATIO * 0.16));
export const tileFullHeight = (w: number) => Math.round(w * TILE_RATIO) + sideOf(w);

// 2.5D tile: drop shadow, a solid warm-ivory rounded "side wall" peeking below
// (the depth), then the printed top face. Solid side gives clean, high-contrast
// thickness (Mahjong-Soul-ish) instead of a washed-out textured copy.
export function makeTile(t: TileView, w: number): Laya.Sprite {
  const h = Math.round(w * TILE_RATIO);
  const side = sideOf(w);
  const r = Math.max(3, Math.round(w * 0.1));
  const sp = new Laya.Sprite();
  const g = sp.graphics;
  g.drawRoundRect(Math.round(w * 0.05), side + Math.round(side * 0.5), w, h, r, r, r, r, "#00000040");      // drop shadow
  g.drawRoundRect(0, side, w, h, r, r, r, r, "#cfc3a3");                                                    // ivory side = the tile's own depth
  const front = Laya.loader.getRes(url("Front"));
  if (front) g.drawTexture(front, 0, 0, w, h);                                                              // top face body
  const face = Laya.loader.getRes(url(faceFile(t)));
  if (face) g.drawTexture(face, 0, 0, w, h);                                                                // printed face
  sp.size(w, h + side);
  return sp;
}

export function makeBack(w: number): Laya.Sprite {
  const h = Math.round(w * TILE_RATIO);
  const side = sideOf(w);
  const r = Math.max(3, Math.round(w * 0.1));
  const sp = new Laya.Sprite();
  const g = sp.graphics;
  g.drawRoundRect(Math.round(w * 0.06), side + Math.round(side * 0.5), w, h, r, r, r, r, "#00000048");
  g.drawRoundRect(0, side, w, h, r, r, r, r, "#0a2c22");          // dark green side
  const back = Laya.loader.getRes(url("Back"));
  if (back) g.drawTexture(back, 0, 0, w, h);
  sp.size(w, h + side);
  return sp;
}
