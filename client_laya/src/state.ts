// Local game model: holds the latest snapshot and applies events incrementally
// so the board stays live between the authoritative snapshots.
import type { Snapshot, SeatView } from "./protocol";

export class GameModel {
  yourSeat = 0;
  seatNames: string[] = ["E", "S", "W", "N"];
  ruleset = "?";
  snap: Snapshot | null = null;
  lastDiscard: { seat: number; id: number } | null = null;

  seat(s: number): SeatView | undefined {
    return this.snap?.seats.find((x) => x.seat === s);
  }

  applyEvent(e: any) {
    const snap = this.snap;
    if (!snap) return;
    switch (e.kind) {
      case "hand_started":
        snap.dealer = e.dealer; snap.round_wind = e.round_wind; snap.hand_number = e.hand_number;
        this.lastDiscard = null; break;
      case "tile_drawn": {
        const s = this.seat(e.seat); if (!s) break;
        s.hand_count = (s.hand_count || 0) + 1; snap.current_seat = e.seat;
        if (e.tile && e.seat === this.yourSeat) { (s.hand ||= []).push(e.tile); snap.last_drawn_tile = e.tile; }
        break;
      }
      case "tile_discarded": {
        const s = this.seat(e.seat); if (!s) break;
        if (e.tile) { (s.discards ||= []).push(e.tile); this.lastDiscard = { seat: e.seat, id: e.tile.id }; }
        if (e.seat === this.yourSeat && e.tile && s.hand) {
          const i = s.hand.findIndex((t) => t.id === e.tile.id);
          if (i >= 0) s.hand.splice(i, 1);
          snap.last_drawn_tile = null;
        } else {
          s.hand_count = Math.max(0, (s.hand_count || 1) - 1);
        }
        if (e.riichi) s.riichi = true;
        break;
      }
      case "riichi_declared": { const s = this.seat(e.seat); if (s) s.riichi = true; break; }
      case "meld_formed": {
        const s = this.seat(e.seat); if (!s) break;
        (s.melds ||= []).push({ meld_type: e.meld_type, tiles: e.tiles || [], called_from: e.called_from });
        this.lastDiscard = null; break;
      }
    }
  }
}
