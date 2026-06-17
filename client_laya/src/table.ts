// TableView: renders the live board into a Laya scene from the GameModel.
// Chunk 1 = upright layout (rotation/animations come next). Full redraw per update.
import type { GameModel } from "./state";
import type { ActionView, TileView, SeatView } from "./protocol";
import { makeTile, makeBack } from "./tiles";

const WINDS = ["", "東", "南", "西", "北"];
export const DESIGN_W = 1280;
export const DESIGN_H = 960;

export class TableView {
  root: Laya.Sprite;
  onDiscard: (t: TileView) => void = () => {};

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

  private pond(discards: TileView[], x: number, y: number, w: number, cols = 6, curId: number | null = null) {
    const { gap } = { gap: 2 };
    const h = Math.round(w * 4 / 3);
    discards.forEach((t, i) => {
      const sp = makeTile(t, w);
      sp.pos(x + (i % cols) * (w + gap), y + Math.floor(i / cols) * (h + gap));
      if (curId != null && t.id === curId) { sp.graphics.drawRect(0, 0, w, h, null, "#e7c46a", 2); }
      this.root.addChild(sp);
    });
  }

  render(model: GameModel, pending: ActionView[] | null) {
    this.root.removeChildren();
    const snap = model.snap;
    if (!snap) return;

    // discardable tile ids (chunk 1: plain discard via hand click)
    const discardable = new Set<number>();
    if (pending) for (const a of pending) if (a.kind === "discard") for (const t of a.tiles || []) if (t.id != null) discardable.add(t.id);

    // ── center well ──
    this.root.graphics.drawRect(510, 380, 260, 200, "#08281e", "#e7c46a55", 1);
    this.text(`${WINDS[snap.round_wind] || "?"} ${snap.hand_number}`, 560, 405, 30, "#e7c46a", true);
    this.text(`山 ${snap.wall_count}   庄 ${WINDS[snap.dealer + 1] || snap.dealer}`, 545, 450, 18, "#9fc4b4");
    this.text("宝牌", 545, 488, 13, "#9fc4b4");
    (snap.dora_indicators || []).forEach((t, i) => { const sp = makeTile(t, 30); sp.pos(545 + i * 34, 508); this.root.addChild(sp); });

    // ── per seat: label + discards; your hand face-up & clickable, others count ──
    for (let rel = 0; rel < 4; rel++) {
      const seatNo = ((model.yourSeat + rel) % 4 + 4) % 4;
      const sv = model.seat(seatNo);
      if (!sv) continue;
      this.renderSeat(rel, seatNo, sv, model, discardable);
    }
  }

  private renderSeat(rel: number, seatNo: number, sv: SeatView, model: GameModel, discardable: Set<number>) {
    const snap = model.snap!;
    const seatWind = WINDS[((seatNo - snap.dealer + 4) % 4) + 1];
    const active = snap.current_seat === seatNo;
    const label = `${seatWind} ${sv.name}${seatNo === model.yourSeat ? "(你)" : ""}  ${sv.points}${sv.riichi ? "  立" : ""}`;
    const curId = model.lastDiscard && model.lastDiscard.seat === seatNo ? model.lastDiscard.id : null;
    const labelColor = active ? "#e7c46a" : "#cfe0d8";

    if (rel === 0) {
      // you: bottom — hand face up + clickable, pond above, label bottom-left
      this.text(label, 40, 905, 18, labelColor, active);
      const hand = sortHand(sv.hand || []);
      const HW = 62, gap = 4;
      const x0 = (DESIGN_W - hand.length * (HW + gap)) / 2;
      const drawnId = snap.last_drawn_tile?.id ?? null;
      hand.forEach((t, i) => {
        const sp = makeTile(t, HW);
        const isDrawn = t.id === drawnId;
        sp.pos(x0 + i * (HW + gap) + (isDrawn ? 14 : 0), 824);
        if (t.id != null && discardable.has(t.id)) {
          const baseY = sp.y;
          sp.on(Laya.Event.CLICK, this, () => this.onDiscard(t));
          sp.on(Laya.Event.MOUSE_OVER, this, () => { sp.y = baseY - 14; });
          sp.on(Laya.Event.MOUSE_OUT, this, () => { sp.y = baseY; });
        }
        this.root.addChild(sp);
      });
      this.pond(sv.discards || [], (DESIGN_W - 6 * 34) / 2, 600, 32, 6, curId);
    } else if (rel === 2) {
      // across (top)
      this.text(label, 540, 30, 18, labelColor, active);
      this.backsRow(sv.hand_count, 480, 60, 26, true);
      this.pond(sv.discards || [], (DESIGN_W - 6 * 30) / 2, 150, 28, 6, curId);
    } else if (rel === 3) {
      // left
      this.text(label, 30, 330, 18, labelColor, active);
      this.backsCol(sv.hand_count, 40, 360, 24);
      this.pond(sv.discards || [], 210, 360, 26, 6, curId);
    } else {
      // right
      this.text(label, 980, 330, 18, labelColor, active);
      this.backsCol(sv.hand_count, 1210, 360, 24);
      this.pond(sv.discards || [], 800, 360, 26, 6, curId);
    }
  }

  private backsRow(count: number, x: number, y: number, w: number, _flip: boolean) {
    for (let i = 0; i < count; i++) { const sp = makeBack(w); sp.pos(x + i * (w + 2), y); this.root.addChild(sp); }
  }
  private backsCol(count: number, x: number, y: number, w: number) {
    const h = Math.round(w * 4 / 3);
    for (let i = 0; i < count; i++) { const sp = makeBack(w); sp.pos(x, y + i * (h * 0.62)); this.root.addChild(sp); }
  }
}

function sortHand(hand: TileView[]): TileView[] {
  const order: Record<string, number> = { m: 0, p: 1, s: 2, z: 3 };
  return [...hand].sort((a, b) => {
    const sa = order[a.code[0]], sb = order[b.code[0]];
    return sa !== sb ? sa - sb : (+a.code.slice(1)) - (+b.code.slice(1));
  });
}
