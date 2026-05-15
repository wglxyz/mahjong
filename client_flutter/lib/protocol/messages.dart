/// Wire protocol DTOs — must stay in sync with server/protocol.py.
///
/// Keep this file editable by hand. When the Python side changes, mirror here.
/// Each class has [fromJson] for parsing inbound messages; outbound messages
/// build maps directly inline (only `decide` and `request_snapshot` exist).

class TileView {
  final String code;     // "m1".."m9", "p1".."p9", "s1".."s9", "z1".."z7"
  final bool red;
  final int? id;
  const TileView({required this.code, this.red = false, this.id});
  factory TileView.fromJson(Map<String, dynamic> j) => TileView(
        code: j['code'] as String,
        red: j['red'] as bool? ?? false,
        id: j['id'] as int?,
      );
  String get assetPath {
    if (red) return 'assets/tiles/${code}r.svg';
    return 'assets/tiles/$code.svg';
  }
}

class MeldView {
  final String meldType;       // "chi" | "pon" | "minkan" | "ankan" | "shouminkan"
  final List<TileView> tiles;
  final int? calledFrom;
  const MeldView({required this.meldType, required this.tiles, this.calledFrom});
  factory MeldView.fromJson(Map<String, dynamic> j) => MeldView(
        meldType: j['meld_type'] as String,
        tiles: (j['tiles'] as List).map((t) => TileView.fromJson(t)).toList(),
        calledFrom: j['called_from'] as int?,
      );
}

class SeatView {
  final int seat;
  final String name;
  final int points;
  final bool riichi;
  final List<MeldView> melds;
  final List<TileView> discards;
  final List<TileView>? hand;   // populated only for own seat
  final int handCount;

  const SeatView({
    required this.seat,
    required this.name,
    required this.points,
    required this.riichi,
    required this.melds,
    required this.discards,
    this.hand,
    required this.handCount,
  });

  factory SeatView.fromJson(Map<String, dynamic> j) => SeatView(
        seat: j['seat'] as int,
        name: j['name'] as String,
        points: j['points'] as int,
        riichi: j['riichi'] as bool? ?? false,
        melds: ((j['melds'] as List?) ?? const [])
            .map((m) => MeldView.fromJson(m))
            .toList(),
        discards: ((j['discards'] as List?) ?? const [])
            .map((t) => TileView.fromJson(t))
            .toList(),
        hand: j.containsKey('hand')
            ? (j['hand'] as List).map((t) => TileView.fromJson(t)).toList()
            : null,
        handCount: j['hand_count'] as int? ?? 0,
      );
}

class ActionView {
  final String id;                       // opaque token; echo back via `decide`
  final String kind;                     // "discard"|"pass"|"chi"|"pon"|"kan"|"tsumo"|"ron"|"riichi"
  final List<TileView> tiles;
  final Map<String, dynamic> extra;
  const ActionView({
    required this.id,
    required this.kind,
    this.tiles = const [],
    this.extra = const {},
  });
  factory ActionView.fromJson(Map<String, dynamic> j) => ActionView(
        id: j['id'] as String,
        kind: j['kind'] as String,
        tiles: ((j['tiles'] as List?) ?? const [])
            .map((t) => TileView.fromJson(t))
            .toList(),
        extra: (j['extra'] as Map?)?.cast<String, dynamic>() ?? const {},
      );
}

class Snapshot {
  final int yourSeat;
  final int roundWind;
  final int handNumber;
  final int dealer;
  final int wallCount;
  final int deadWallCount;
  final List<TileView> doraIndicators;
  final List<SeatView> seats;
  final int? currentSeat;
  final String? phase;
  final TileView? lastDrawnTile;

  const Snapshot({
    required this.yourSeat,
    required this.roundWind,
    required this.handNumber,
    required this.dealer,
    required this.wallCount,
    required this.deadWallCount,
    required this.doraIndicators,
    required this.seats,
    required this.currentSeat,
    required this.phase,
    required this.lastDrawnTile,
  });

  factory Snapshot.fromJson(Map<String, dynamic> j) => Snapshot(
        yourSeat: j['your_seat'] as int,
        roundWind: j['round_wind'] as int,
        handNumber: j['hand_number'] as int,
        dealer: j['dealer'] as int,
        wallCount: j['wall_count'] as int,
        deadWallCount: j['dead_wall_count'] as int? ?? 0,
        doraIndicators: ((j['dora_indicators'] as List?) ?? const [])
            .map((t) => TileView.fromJson(t))
            .toList(),
        seats: (j['seats'] as List).map((s) => SeatView.fromJson(s)).toList(),
        currentSeat: j['current_seat'] as int?,
        phase: j['phase'] as String?,
        lastDrawnTile: j['last_drawn_tile'] != null
            ? TileView.fromJson(j['last_drawn_tile'] as Map<String, dynamic>)
            : null,
      );
}

class Welcome {
  final int yourSeat;
  final List<String> seats;
  final String ruleset;
  const Welcome({required this.yourSeat, required this.seats, required this.ruleset});
  factory Welcome.fromJson(Map<String, dynamic> j) => Welcome(
        yourSeat: j['your_seat'] as int,
        seats: (j['seats'] as List).map((s) => s as String).toList(),
        ruleset: j['ruleset'] as String,
      );
}

class HandEnded {
  final String result;             // "win" | "drawn"
  final int? winner;
  final int? loser;
  final int score;
  final int? han;
  final int? fu;
  final List<MapEntry<String, int>> yaku;
  final List<int> winners;         // ≥1 entry for ron/tsumo (≥2 for double-ron)
  final String? abortReason;       // set on aborted draws (nine_terminals, four_winds, ...)
  const HandEnded({
    required this.result,
    required this.winner,
    required this.loser,
    required this.score,
    required this.han,
    required this.fu,
    required this.yaku,
    this.winners = const [],
    this.abortReason,
  });
  factory HandEnded.fromJson(Map<String, dynamic> j) => HandEnded(
        result: j['result'] as String,
        winner: j['winner'] as int?,
        loser: j['loser'] as int?,
        score: j['score'] as int? ?? 0,
        han: j['han'] as int?,
        fu: j['fu'] as int?,
        yaku: ((j['yaku'] as List?) ?? const [])
            .map((e) => MapEntry(e[0] as String, e[1] as int))
            .toList(),
        winners: ((j['winners'] as List?) ?? const []).map((e) => e as int).toList(),
        abortReason: j['abort_reason'] as String?,
      );
}

/// Generic event wrapper. We don't strictly type each event kind here — the game
/// state inspects [kind] and routes per-kind animation. Add fields by reading [data].
class GameEvent {
  final String kind;
  final Map<String, dynamic> data;
  const GameEvent({required this.kind, required this.data});
  factory GameEvent.fromJson(Map<String, dynamic> j) {
    final inner = (j['event'] as Map).cast<String, dynamic>();
    return GameEvent(kind: inner['kind'] as String, data: inner);
  }
}

/// Sent once after the entire match ends (all configured rounds played).
class MatchEnded {
  final Map<int, int> finalPoints;
  final List<Map<String, dynamic>> handResults;
  const MatchEnded({required this.finalPoints, required this.handResults});
  factory MatchEnded.fromJson(Map<String, dynamic> j) => MatchEnded(
        finalPoints: ((j['final_points'] as Map?) ?? const {})
            .map((k, v) => MapEntry(int.parse(k as String), v as int)),
        handResults: ((j['hand_results'] as List?) ?? const [])
            .map((e) => (e as Map).cast<String, dynamic>())
            .toList(),
      );
}
