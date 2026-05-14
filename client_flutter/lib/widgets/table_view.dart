import 'package:flutter/material.dart';

import '../protocol/messages.dart';
import '../theme.dart';
import 'discard_grid.dart';
import 'hand_view.dart';
import 'riichi_stick.dart';
import 'seat_panel.dart';
import 'tile.dart';

/// The main table: 4 seats arranged around the centre.
///
///   you = bottom (rotation 0)
///   right = right (rotation 0.25 — rotated 90° CW)
///   across = top (rotation 0.5)
///   left = left (rotation 0.75 — rotated 270° CW)
///
/// Centre shows wall count, dora indicators, round wind.
class TableView extends StatelessWidget {
  final Snapshot snap;
  final void Function(TileView tile)? onTapMyTile;
  final Set<int> highlightHandIds;

  const TableView({
    super.key,
    required this.snap,
    this.onTapMyTile,
    this.highlightHandIds = const {},
  });

  @override
  Widget build(BuildContext context) {
    final you = snap.yourSeat;
    final seats = snap.seats;
    SeatView seatFor(int rel) => seats.firstWhere((s) => s.seat == (you + rel) % 4);

    final me = seatFor(0);
    final right = seatFor(1);
    final across = seatFor(2);
    final left = seatFor(3);

    return Container(
      decoration: BoxDecoration(
        gradient: RadialGradient(
          radius: 0.9,
          colors: [
            AppColors.tableFelt,
            AppColors.tableFeltDeep,
          ],
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: LayoutBuilder(
          builder: (ctx, box) {
            return Stack(
              children: [
                // top — across
                Positioned(
                  top: 0,
                  left: 0,
                  right: 0,
                  child: Center(
                    child: _SeatGroup(
                      seat: across,
                      side: Side.top,
                      isActive: snap.currentSeat == across.seat,
                      isDealer: snap.dealer == across.seat,
                      seatWind: _seatWind(across.seat),
                    ),
                  ),
                ),
                // left — left
                Positioned(
                  top: 0,
                  bottom: 0,
                  left: 0,
                  child: Center(
                    child: _SeatGroup(
                      seat: left,
                      side: Side.left,
                      isActive: snap.currentSeat == left.seat,
                      isDealer: snap.dealer == left.seat,
                      seatWind: _seatWind(left.seat),
                    ),
                  ),
                ),
                // right — right
                Positioned(
                  top: 0,
                  bottom: 0,
                  right: 0,
                  child: Center(
                    child: _SeatGroup(
                      seat: right,
                      side: Side.right,
                      isActive: snap.currentSeat == right.seat,
                      isDealer: snap.dealer == right.seat,
                      seatWind: _seatWind(right.seat),
                    ),
                  ),
                ),
                // centre — wall + dora
                Center(child: _Centre(snap: snap)),
                // bottom — me
                Positioned(
                  left: 0,
                  right: 0,
                  bottom: 0,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 30, vertical: 6),
                        child: DiscardGrid(discards: me.discards, tileWidth: 30),
                      ),
                      if (me.riichi)
                        const Padding(
                          padding: EdgeInsets.symmetric(vertical: 4),
                          child: Center(child: RiichiStick()),
                        ),
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 4),
                        child: Row(
                          children: [
                            SeatPanel(
                              seat: me,
                              isYou: true,
                              isActive: snap.currentSeat == me.seat,
                              isDealer: snap.dealer == me.seat,
                              seatWind: _seatWind(me.seat),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Align(
                                alignment: Alignment.centerRight,
                                child: HandView(
                                  tiles: me.hand ?? const [],
                                  justDrewId: snap.lastDrawnTile?.id,
                                  onTapTile: onTapMyTile,
                                  highlightIds: highlightHandIds,
                                  tileWidth: 52,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            );
          },
        ),
      ),
    );
  }

  int _seatWind(int seat) => ((seat - snap.dealer) % 4) + 1;
}

enum Side { top, left, right }

class _SeatGroup extends StatelessWidget {
  final SeatView seat;
  final Side side;
  final bool isActive;
  final bool isDealer;
  final int seatWind;

  const _SeatGroup({
    required this.seat,
    required this.side,
    required this.isActive,
    required this.isDealer,
    required this.seatWind,
  });

  @override
  Widget build(BuildContext context) {
    final hand = Row(
      mainAxisSize: MainAxisSize.min,
      children: List.generate(seat.handCount, (i) {
        return Padding(
          padding: EdgeInsets.only(left: i == 0 ? 0 : 2),
          child: const TileFace(tile: null, width: 22),
        );
      }),
    );

    final rotation = switch (side) {
      Side.top => 0.5,
      Side.left => 0.75,
      Side.right => 0.25,
    };

    Widget content = Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        hand,
        const SizedBox(height: 6),
        SeatPanel(
          seat: seat,
          isYou: false,
          isActive: isActive,
          isDealer: isDealer,
          seatWind: seatWind,
        ),
        if (seat.riichi) ...[
          const SizedBox(height: 4),
          const RiichiStick(width: 80),
        ],
        const SizedBox(height: 6),
        DiscardGrid(
          discards: seat.discards,
          tileWidth: 24,
        ),
      ],
    );

    return RotatedBox(quarterTurns: (rotation * 4).round(), child: content);
  }
}

class _Centre extends StatelessWidget {
  final Snapshot snap;
  const _Centre({required this.snap});

  static const _winds = ['', '東', '南', '西', '北'];

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.surfaceRaised.withValues(alpha: 0.85),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.goldDim.withValues(alpha: 0.5), width: 1),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.4),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            '${_winds[snap.roundWind]} ${snap.handNumber}',
            style: const TextStyle(
              color: AppColors.goldBright,
              fontSize: 28,
              fontWeight: FontWeight.w700,
              letterSpacing: 4,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            '牌山 ${snap.wallCount}',
            style: const TextStyle(
              color: AppColors.textSecondary,
              fontSize: 12,
              letterSpacing: 2,
            ),
          ),
          if (snap.doraIndicators.isNotEmpty) ...[
            const SizedBox(height: 10),
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                for (final d in snap.doraIndicators)
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 2),
                    child: TileFace(tile: d, width: 28),
                  ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}
