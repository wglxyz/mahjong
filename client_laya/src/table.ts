// TableView: renders the live board + action buttons into a Laya scene.
// Upright layout (rotation later). Discard/draw tween in; only newly-seen tiles animate.
import type { GameModel } from "./state";
import type { ActionView, TileView, SeatView } from "./protocol";
import { makeTile, makeBack } from "./tiles";

const WINDS = ["", "東", "南", "西", "北"];
export const DESIGN_W = 1280;
export const DESIGN_H = 960;
const KIND_LABEL: Record<string, string> = { pass: "过", chi: "吃", pon: "碰", kan: "杠", tsumo: "自摸", ron: "荣和", riichi: "立直", abort: "流局" };

export class TableView {
  root: Laya.Sprite;
  onDecide: (id: string) => void = () => {};

  private seenDiscards = new Set<number>();
  private animatedDraws = new Set<number>();
  private riichiArmed = false;
  private handKey = "";
  private pending: ActionView[] | null = null;
  private model: GameModel | null = null;

  constructor(stage: Laya.Sprite) {
    this.root = new Laya.Sprite();
    stage.addChild(this.root);
  }

  private text(s: string, x: number, y: number, size: number, color = "#f2efe6", bold = false): Laya.Text {
    const t = new Laya.Text();
    t.text = s; t.fontSize = size; t.color = color; t.bold = bold; t.pos(x, y);
    this.root.addChild(t);
    return t;
  }

  render(model: GameModel, pending: ActionView[] | null) {
    this.model = model;
    this.pending = pending;
    const snap = model.snap;
    if (!snap) return;

    // reset per-hand animation memory when the hand changes
    const hk = `${snap.round_wind}-${snap.hand_number}`;
    if (hk !== this.handKey) { this.handKey = hk; this.seenDiscards.clear(); this.animatedDraws.clear(); this.riichiArmed = false; }

    this.root.removeChildren();

    // ── center well ──
    this.root.graphics.drawRect(510, 380, 260, 200, "#08281e", "#e7c46a55", 1);
    this.text(`${WINDS[snap.round_wind] || "?"} ${snap.hand_number}`, 560, 405, 30, "#e7c46a", true);
    this.text(`山 ${snap.wall_count}   庄 ${WINDS[snap.dealer + 1] || snap.dealer}`, 545, 450, 18, "#9fc4b4");
    this.text("宝牌", 545, 488, 13, "#9fc4b4");
    (snap.dora_indicators || []).forEach((t, i) => { const sp = makeTile(t, 30); sp.pos(545 + i * 34, 508); this.root.addChild(sp); });

    for (let rel = 0; rel < 4; rel++) {
      const seatNo = ((model.yourSeat + rel) % 4 + 4) % 4;
      const sv = model.seat(seatNo);
      if (sv) this.renderSeat(rel, seatNo, sv, model);
    }

    this.renderActionBar();
  }

  // which kind a hand-tile click performs right now
  private handActionFor(t: TileView): ActionView | undefined {
    if (!this.pending) return undefined;
    const kind = this.riichiArmed ? "riichi" : "discard";
    return this.pending.find((a) => a.kind === kind && (a.tiles || []).some((x) => x.id === t.id));
  }

  private renderSeat(rel: number, seatNo: number, sv: SeatView, model: GameModel) {
    const snap = model.snap!;
    const seatWind = WINDS[((seatNo - snap.dealer + 4) % 4) + 1];
    const active = snap.current_seat === seatNo;
    const label = `${seatWind} ${sv.name}${seatNo === model.yourSeat ? "(你)" : ""}  ${sv.points}${sv.riichi ? "  立" : ""}`;
    const curId = model.lastDiscard && model.lastDiscard.seat === seatNo ? model.lastDiscard.id : null;
    const labelColor = active ? "#e7c46a" : "#cfe0d8";

    if (rel === 0) {
      this.text(label, 40, 905, 18, labelColor, active);
      const hand = sortHand(sv.hand || []);
      const HW = 62, gap = 4;
      const x0 = (DESIGN_W - hand.length * (HW + gap)) / 2;
      const drawnId = snap.last_drawn_tile?.id ?? null;
      hand.forEach((t, i) => {
        const sp = makeTile(t, HW);
        const isDrawn = t.id === drawnId;
        const ty = 824;
        sp.pos(x0 + i * (HW + gap) + (isDrawn ? 14 : 0), ty);
        const act = this.handActionFor(t);
        if (act) {
          const baseY = sp.y;
          sp.on(Laya.Event.CLICK, this, () => this.onDecide(act.id));
          sp.on(Laya.Event.MOUSE_OVER, this, () => { sp.y = baseY - 14; });
          sp.on(Laya.Event.MOUSE_OUT, this, () => { sp.y = baseY; });
        }
        this.root.addChild(sp);
        if (isDrawn && t.id != null && !this.animatedDraws.has(t.id)) {
          this.animatedDraws.add(t.id);
          sp.y = ty - 26; sp.alpha = 0.3;
          Laya.Tween.to(sp, { y: ty, alpha: 1 }, 420, Laya.Ease.backOut);
        }
      });
      this.pond(sv.discards || [], (DESIGN_W - 6 * 34) / 2, 600, 32, curId);
    } else if (rel === 2) {
      this.text(label, 540, 30, 18, labelColor, active);
      this.backsRow(sv.hand_count, 480, 60, 26);
      this.pond(sv.discards || [], (DESIGN_W - 6 * 30) / 2, 150, 28, curId);
    } else if (rel === 3) {
      this.text(label, 30, 330, 18, labelColor, active);
      this.backsCol(sv.hand_count, 40, 360, 24);
      this.pond(sv.discards || [], 210, 360, 26, curId);
    } else {
      this.text(label, 980, 330, 18, labelColor, active);
      this.backsCol(sv.hand_count, 1210, 360, 24);
      this.pond(sv.discards || [], 800, 360, 26, curId);
    }
  }

  private pond(discards: TileView[], x: number, y: number, w: number, curId: number | null) {
    const cols = 6, gap = 2, h = Math.round(w * 4 / 3);
    discards.forEach((t, i) => {
      const sp = makeTile(t, w);
      const tx = x + (i % cols) * (w + gap), ty = y + Math.floor(i / cols) * (h + gap + 4);
      sp.pos(tx, ty);
      if (curId != null && t.id === curId) sp.graphics.drawRect(0, 0, w, h, null, "#e7c46a", 2);
      this.root.addChild(sp);
      if (t.id != null && !this.seenDiscards.has(t.id)) {
        this.seenDiscards.add(t.id);
        sp.alpha = 0; sp.y = ty - 22;
        Laya.Tween.to(sp, { alpha: 1, y: ty }, 280, Laya.Ease.cubicOut);
      }
    });
  }

  private backsRow(count: number, x: number, y: number, w: number) {
    for (let i = 0; i < count; i++) { const sp = makeBack(w); sp.pos(x + i * (w + 2), y); this.root.addChild(sp); }
  }
  private backsCol(count: number, x: number, y: number, w: number) {
    const h = Math.round(w * 4 / 3);
    for (let i = 0; i < count; i++) { const sp = makeBack(w); sp.pos(x, y + i * (h * 0.62)); this.root.addChild(sp); }
  }

  // ── action buttons (in-canvas, so it works in the WeChat mini-game too) ──
  private renderActionBar() {
    const p = this.pending;
    if (!p || !p.length) return;
    const others = p.filter((a) => a.kind !== "discard" && a.kind !== "riichi");
    const hasRiichi = p.some((a) => a.kind === "riichi");

    const btns: Laya.Sprite[] = [];
    if (hasRiichi) {
      btns.push(this.button(this.riichiArmed ? "取消立直" : "立直", "#c79a2e", "#1a1a1a", () => {
        this.riichiArmed = !this.riichiArmed; this.render(this.model!, this.pending);
      }));
    }
    for (const a of others) {
      let label = KIND_LABEL[a.kind] || a.kind;
      if (a.kind === "kan" && a.extra?.kan_kind) label += `(${a.extra.kan_kind})`;
      const [bg, fg] = a.kind === "pass" ? ["#5a6b64", "#fff"]
        : a.kind === "tsumo" || a.kind === "ron" ? ["#c0392b", "#fff"]
        : ["#d2882a", "#2a1a05"]; // chi/pon/kan
      btns.push(this.button(label, bg, fg, () => this.onDecide(a.id)));
    }
    // lay out centered at bottom
    const gap = 14;
    const totalW = btns.reduce((s, b) => s + b.width, 0) + gap * (btns.length - 1);
    let x = (DESIGN_W - totalW) / 2;
    for (const b of btns) { b.pos(x, 748); this.root.addChild(b); x += b.width + gap; }
  }

  private button(label: string, bg: string, fg: string, onClick: () => void): Laya.Sprite {
    const b = new Laya.Sprite();
    const t = new Laya.Text();
    t.text = label; t.fontSize = 24; t.bold = true; t.color = fg;
    const padX = 20, padY = 11;
    const w = Math.ceil(t.width) + padX * 2, h = Math.ceil(t.height) + padY * 2;
    b.graphics.drawRoundRect(0, 0, w, h, 10, 10, 10, 10, bg);
    t.pos(padX, padY); b.addChild(t);
    b.size(w, h);
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
