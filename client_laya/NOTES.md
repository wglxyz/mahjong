# client_laya — gotchas & hard-won notes

LayaAir 3.4, **code-first, no IDE**. The IDE normally hides a lot of this; doing it
by hand means we hit (and must remember) the following.

## Engine setup

- **No usable npm package.** Engine is vendored from the GitHub release
  `LayaAir_3.4.0_libs.zip` as global `<script>` files in `public/libs/`; types come
  from `types/LayaAir.d.ts` (global `declare class/namespace Laya`).
- **Script load order matters (eval-time):** `core → webgl_2D → d3 → webgl_3D`.
  - `laya.webgl_2D.js` must load **after** `laya.core.js`, or `Laya.init` throws
    `Cannot read properties of undefined (reading 'createEngine')`
    (core alone registers no render device). `laya.opengl_2D.js` is the native/conch
    path, **not** the browser path — don't use it.
  - `laya.webgl_3D.js` extends classes from `laya.d3.js`, so d3 must precede it,
    else `Class extends value undefined`.
  - `tools/check-engine-load.cjs` catches these eval-order bugs in Node (no browser):
    `node tools/check-engine-load.cjs laya.core.js laya.webgl_2D.js laya.d3.js laya.webgl_3D.js`
- **SVG loading:** Laya's loader picks a parser by file suffix and has **no `.svg`
  parser** ("unsupported suffix"). Load tiles with `type: Laya.Loader.IMAGE` so the
  `<img>`-based image loader rasterizes the SVG. Then use the texture via
  `(tex as Laya.Texture).bitmap` (a BaseTexture) → `material.albedoTexture`.
- Anti-alias: `Config.isAntialias`, `Config.useRetinalCanvas`, `Config3D.pixelRatio`
  (cap ~2), `camera.msaa = true`.

## Custom 3D meshes (no IDE = build vertices by hand)

- `(Laya.PrimitiveMesh as any)._createMesh(decl, Float32Array, Uint16Array)` with
  `decl = (Laya as any).VertexMesh.getVertexDeclaration("POSITION,NORMAL,UV,TANGENT")`.
- Vertex layout = pos(3) + normal(3) + uv(2) + tangent(4) = **12 floats / vertex**.
- `PrimitiveMesh.createQuad` faces **+Z**, UV origin top-left.
- A `DirectionLight` is a **Component**: `sprite3d.addComponent(Laya.DirectionLightCom)`,
  then set `.color` / `.intensity` and rotate the host `Sprite3D`.
- `Material.cull = Laya.RenderState.CULL_NONE` to render back faces.

## Tile look — how Mahjong Soul / a real tile is actually made

Researched (Blender breakdown + PBR refs). The look comes from, in order of impact:

1. **One rounded tile, beveled edges** — a single box with a ~1mm bevel on all
   edges. The rounded/beveled edge is essential; sharp boxes look like dice.
2. **Two material regions on the one tile** (a "loop cut" splits it): cream/white
   **front** face + golden body (~`#e9b501`). Not two separate stacked meshes.
3. **Semi-gloss PBR** (real tile ≈ roughness 0.25): a **specular highlight**.
4. **Lighting so the beveled edge catches that highlight** — soft ambient fill +
   one key directional from upper-front. **The highlight riding the bevel IS the
   thickness/3D cue.**
5. Engraved symbols = a normal/bump map (we currently use a flat symbol quad).

### Pitfalls we burned time on (don't repeat)

- ❌ **`UnlitMaterial` for the tile body** — unlit = no shading = every face the same
  flat colour = zero perceived thickness. Use `BlinnPhongMaterial` (lit) with
  `specularColor` + `shininess`.
- ❌ **Contour lines (`PixelLineSprite3D`) to "draw" the edges** — looks like a cheap
  cartoon/toy, not a tile. The edge should be a lit bevel highlight, not a black line.
- ❌ **Two stacked blocks with a gap** (white block floating a hair above amber) —
  causes a visible seam / double-edge / z-fighting. Seat the front block **flush**
  (`z = (BD + FD)/2`) so it reads as one continuous rounded tile, or build it as one
  mesh with two material regions.
- ❌ **Relying on shading alone with low ambient** — goes too dark before thickness
  reads. Keep ambient moderate (~0.6) and get the cue from the specular bevel
  highlight instead.
- Verification is **screenshot-driven** — this box is headless (no browser here).
  Drop PNGs in `/tmp`, they get Read and compared against the Majsoul reference.

## Workflow gotcha (bites every build)

- `npm run build` is run from `client_laya/`, so the shell cwd drifts there.
  **git must run from the repo root** `/root/avid/mahjong` — otherwise paths resolve
  to `client_laya/client_laya/src/...` and the commit fails
  (`pathspec ... did not match any files`). Re-run `git add client_laya/... && commit`
  from the repo root.

## Serving

Python server (`server/server.py`) serves the Vite build (`client_laya/dist`,
`base:/laya/`) at `/laya/`, same origin as the WebSocket. Old HTML client still at `/`.
gzip + immutable cache for static assets; engine cache-busted with `?v=lay340`.
Build: `cd client_laya && npm install && npm run build`.
