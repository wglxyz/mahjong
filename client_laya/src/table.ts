// TableView: live board + action buttons in a Laya scene.
// Tiles that move/animate (your hand + every discard) are kept as persistent
// sprites keyed by id (reconcile), so their tweens are never cut short by a
// re-render. Static chrome (well, labels, dora, opponent backs) and the action
// buttons are cheap and rebuilt each frame.
import type { GameModel } from "./state";
import type { ActionView, TileView, SeatView } from "./protocol";
import { makeTile, makeBack, tileFullHeight } from "./tiles";

const WINDS = ["", "東", "南", "西", "北"];
export const DESIGN_W = 1280;
export const DESIGN_H = 960;
const KIND_LABEL: Record<string, string> = { pass: "过", chi: "吃", pon: "碰", kan: "杠", tsumo: "自摸", ron: "荣和", riichi: "立直", abort: "流局" };

interface Placed { key: string; tile: TileView; x: number; y: number; w: number; kind: "hand" | "discard"; drawn?: boolean; act?: ActionView; }

export class TableView {
  root: Laya.Sprite;
  onDecide: (id: string) => void = () => {};

  private bg: Laya.Sprite;   // well / labels / dora / opponent backs / highlight
  private dyn: Laya.Sprite;  // animated tiles (your hand + discards), keyed by id
  private ui: Laya.Sprite;   // action buttons
  private live = new Map<string, Laya.Sprite>();

  private seenDiscards = new Set<number>();
  private animatedDraws = new Set<number>();
  private riichiArmed = false;
  private handKey = "";
  private pending: ActionView[] | null = null;
  private model: GameModel | null = null;

  constructor(stage: Laya.Sprite) {
    this.root = new Laya.Sprite();
    stage.addChild(this.root);
    this.bg = new Laya.Sprite(); this.dyn = new Laya.Sprite(); this.ui = new Laya.Sprite();
    this.root.addChild(this.bg); this.root.addChild(this.dyn); this.root.addChild(this.ui);
  }

  private text(parent: Laya.Sprite, s: string, x: number, y: number, size: number, color = "#f2efe6", bold = false) {
    const t = new Laya.Text();
    t.text = s; t.fontSize = size; t.color = color; t.bold = bold; t.pos(x, y);
    parent.addChild(t);
  }

  render(model: GameModel, pending: ActionView[] | null) {
    this.model = model; this.pending = pending;
    const snap = model.snap;
    if (!snap) return;

    const hk = `${snap.round_wind}-${snap.hand_number}`;
    if (hk !== this.handKey) { this.handKey = hk; this.seenDiscards.clear(); this.animatedDraws.clear(); this.riichiArmed = false; }

    this.bg.removeChildren();
    this.ui.removeChildren();

    // ── center well ──
    this.bg.graphics.clear();
    this.bg.graphics.drawRect(510, 380, 260, 200, "#08281e", "#e7c46a55", 1);
    this.text(this.bg, `${WINDS[snap.round_wind] || "?"} ${snap.hand_number}`, 560, 405, 30, "#e7c46a", true);
    this.text(this.bg, `山 ${snap.wall_count}   庄 ${WINDS[snap.dealer + 1] || snap.dealer}`, 545, 450, 18, "#9fc4b4");
    this.text(this.bg, "宝牌", 545, 488, 13, "#9fc4b4");
    (snap.dora_indicators || []).forEach((t, i) => { const sp = makeTile(t, 30); sp.pos(545 + i * 34, 508); this.bg.addChild(sp); });

    // ── collect placed (animated) tiles + draw static chrome ──
    const placed: Placed[] = [];
    for (let rel = 0; rel < 4; rel++) {
      const seatNo = ((model.yourSeat + rel) % 4 + 4) % 4;
      const sv = model.seat(seatNo);
      if (sv) this.layoutSeat(rel, seatNo, sv, model, placed);
    }

    this.reconcile(placed);
    this.renderActionBar();
  }

  private handActionFor(t: TileView): ActionView | undefined {
    if (!this.pending) return undefined;
    const kind = this.riichiArmed ? "riichi" : "discard";
    return this.pending.find((a) => a.kind === kind && (a.tiles || []).some((x) => x.id === t.id));
  }

  private layoutSeat(rel: number, seatNo: number, sv: SeatView, model: GameModel, placed: Placed[]) {
    const snap = model.snap!;
    const seatWind = WINDS[((seatNo - snap.dealer + 4) % 4) + 1];
    const active = snap.current_seat === seatNo;
    const label = `${seatWind} ${sv.name}${seatNo === model.yourSeat ? "(你)" : ""}  ${sv.points}${sv.riichi ? "  立" : ""}`;
    const curId = model.lastDiscard && model.lastDiscard.seat === seatNo ? model.lastDiscard.id : null;
    const labelColor = active ? "#e7c46a" : "#cfe0d8";

    const pondCfg: Record<number, { x: number; y: number; w: number }> = {
      0: { x: (DESIGN_W - 6 * 27) / 2, y: 592, w: 26 },
      2: { x: (DESIGN_W - 6 * 27) / 2, y: 140, w: 26 },
      3: { x: 200, y: 352, w: 24 },
      1: { x: 812, y: 352, w: 24 },
    };

    if (rel === 0) {
      this.text(this.bg, label, 40, 905, 18, labelColor, active);
      const hand = sortHand(sv.hand || []);
      const HW = 62, gap = 4;
      const x0 = (DESIGN_W - hand.length * (HW + gap)) / 2;
      const drawnId = snap.last_drawn_tile?.id ?? null;
      hand.forEach((t, i) => {
        const drawn = t.id === drawnId;
        placed.push({ key: "h" + t.id, tile: t, x: x0 + i * (HW + gap) + (drawn ? 14 : 0), y: 824, w: HW, kind: "hand", drawn, act: this.handActionFor(t) });
      });
    } else {
      const lp: Record<number, [number, number, number, number]> = { 2: [540, 24, 490, 52], 3: [24, 322, 36, 352], 1: [980, 322, 1216, 352] };
      const [lx, ly, bx, by] = lp[rel];
      this.text(this.bg, label, lx, ly, 18, labelColor, active);
      if (rel === 2) this.backsRow(sv.hand_count, bx, by, 24);
      else this.backsCol(sv.hand_count, bx, by, 22);
    }

    // discards (animated tiles)
    const { x, y, w } = pondCfg[rel];
    const cols = 6, gap = 2, rowH = tileFullHeight(w) + gap, h = Math.round(w * 4 / 3);
    (sv.discards || []).forEach((t, i) => {
      const tx = x + (i % cols) * (w + gap), ty = y + Math.floor(i / cols) * rowH;
      placed.push({ key: "d" + t.id, tile: t, x: tx, y: ty, w, kind: "discard" });
      if (curId != null && t.id === curId) this.bg.graphics.drawRect(tx - 1, ty - 1, w + 2, h + 2, null, "#e7c46a", 2);
    });
  }

  // keyed reconcile: reuse persistent sprites so in-flight tweens survive
  private reconcile(placed: Placed[]) {
    const want = new Set(placed.map((p) => p.key));
    for (const [key, sp] of this.live) if (!want.has(key)) { Laya.Tween.clearAll(sp); sp.removeSelf(); this.live.delete(key); }
    for (const p of placed) {
      let sp = this.live.get(p.key);
      const created = !sp;
      if (!sp) { sp = makeTile(p.tile, p.w); sp.name = p.key; this.dyn.addChild(sp); this.live.set(p.key, sp); }
      sp.offAll();
      if (p.kind === "hand" && p.act) {
        const baseY = p.y;
        sp.on(Laya.Event.CLICK, this, () => this.onDecide(p.act!.id));
        sp.on(Laya.Event.MOUSE_OVER, this, () => { sp!.y = baseY - 14; });
        sp.on(Laya.Event.MOUSE_OUT, this, () => { sp!.y = baseY; });
      }
      // position (no tween for reused unless it's a fresh appear)
      if (created) {
        sp.pos(p.x, p.y);
        if (p.kind === "discard" && p.tile.id != null && !this.seenDiscards.has(p.tile.id)) {
          this.seenDiscards.add(p.tile.id);
          sp.alpha = 0; sp.y = p.y - 24;
          Laya.Tween.to(sp, { alpha: 1, y: p.y }, 320, Laya.Ease.cubicOut);
        } else if (p.kind === "hand" && p.drawn && p.tile.id != null && !this.animatedDraws.has(p.tile.id)) {
          this.animatedDraws.add(p.tile.id);
          sp.alpha = 0.3; sp.y = p.y - 30;
          Laya.Tween.to(sp, { alpha: 1, y: p.y }, 520, Laya.Ease.backOut);
        }
      } else {
        sp.pos(p.x, p.y); sp.alpha = 1;
      }
    }
  }

  private backsRow(count: number, x: number, y: number, w: number) {
    for (let i = 0; i < count; i++) { const sp = makeBack(w); sp.pos(x + i * (w + 2), y); this.bg.addChild(sp); }
  }
  private backsCol(count: number, x: number, y: number, w: number) {
    const h = Math.round(w * 4 / 3);
    for (let i = 0; i < count; i++) { const sp = makeBack(w); sp.pos(x, y + i * (h * 0.62)); this.bg.addChild(sp); }
  }

  private renderActionBar() {
    const p = this.pending;
    if (!p || !p.length) return;
    const others = p.filter((a) => a.kind !== "discard" && a.kind !== "riichi");
    const hasRiichi = p.some((a) => a.kind === "riichi");
    const btns: Laya.Sprite[] = [];
    if (hasRiichi) btns.push(this.button(this.riichiArmed ? "取消立直" : "立直", "#c79a2e", "#1a1a1a", () => { this.riichiArmed = !this.riichiArmed; this.render(this.model!, this.pending); }));
    for (const a of others) {
      let label = KIND_LABEL[a.kind] || a.kind;
      if (a.kind === "kan" && a.extra?.kan_kind) label += `(${a.extra.kan_kind})`;
      const [bg, fg] = a.kind === "pass" ? ["#5a6b64", "#fff"] : a.kind === "tsumo" || a.kind === "ron" ? ["#c0392b", "#fff"] : ["#d2882a", "#2a1a05"];
      btns.push(this.button(label, bg, fg, () => this.onDecide(a.id)));
    }
    const gap = 14;
    const totalW = btns.reduce((s, b) => s + b.width, 0) + gap * (btns.length - 1);
    let x = DESIGN_W - 40 - totalW;
    for (const b of btns) { b.pos(x, 726); this.ui.addChild(b); x += b.width + gap; }
  }

  private button(label: string, bg: string, fg: string, onClick: () => void): Laya.Sprite {
    const fs = 26, padX = 22, padY = 12;
    let tw = 0;
    for (const ch of label) tw += ch.charCodeAt(0) > 255 ? fs : Math.round(fs * 0.55);
    const w = tw + padX * 2, h = fs + padY * 2;
    const b = new Laya.Sprite();
    b.graphics.drawRoundRect(0, 0, w, h, 11, 11, 11, 11, bg);
    const t = new Laya.Text();
    t.text = label; t.fontSize = fs; t.bold = true; t.color = fg;
    t.width = tw; t.height = fs + 4; t.align = "center"; t.valign = "middle"; t.pos(padX, padY - 2);
    b.addChild(t); b.size(w, h);
    b.on(Laya.Event.CLICK, this, onClick);
    return b;
  }
}

function sortHand(hand: TileView[]): TileView[] {
  const order: Record<string, number> = { m: 0, p: 1, s: 2, z: 3 };
  return [...hand].sort((a, b) => {
    const sa = order[a.code[0]], sb = order[b.code[0]];
    return sa !== sb ? sa - sb : (+a.code.slice(1)) - (+b.code.slice(1));
  });
}
