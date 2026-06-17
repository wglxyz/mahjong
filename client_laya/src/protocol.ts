// Wire types mirroring server/protocol.py (only the fields the client uses).

export interface TileView { code: string; red?: boolean; id?: number; }
export interface MeldView { meld_type: string; tiles: TileView[]; called_from?: number | null; }
export interface SeatView {
  seat: number; name: string; points: number; riichi: boolean;
  melds: MeldView[]; discards: TileView[]; hand?: TileView[]; hand_count: number;
}
export interface Snapshot {
  type: "snapshot";
  your_seat: number; round_wind: number; hand_number: number; dealer: number;
  wall_count: number; dead_wall_count: number;
  dora_indicators: TileView[]; seats: SeatView[];
  current_seat: number | null; phase: string | null; last_drawn_tile: TileView | null;
}
export interface ActionView { id: string; kind: string; tiles?: TileView[]; extra?: Record<string, any>; }

export interface WelcomeMsg { type: "welcome"; your_seat: number; seats: string[]; ruleset: string; }
export interface EventMsg { type: "event"; event: any; }
export interface DecisionMsg { type: "decision"; actions: ActionView[]; }
export interface HandEndedMsg {
  type: "hand_ended"; result: "win" | "drawn"; winner: number | null; loser: number | null;
  score: number; han: number | null; fu: number | null; yaku: [string, number][];
  winners: number[]; abort_reason?: string | null;
}
export interface MatchEndedMsg { type: "match_ended"; final_points: Record<string, number>; hand_results: any[]; }

export type ServerMsg =
  | WelcomeMsg | Snapshot | EventMsg | DecisionMsg | HandEndedMsg | MatchEndedMsg
  | { type: "error"; error: string };
