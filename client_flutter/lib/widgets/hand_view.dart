import 'package:flutter/material.dart';

import '../protocol/messages.dart';
import 'animated_tile.dart';
import 'tile.dart';

/// Player's own hand: 13 tiles laid out + just-drawn tile offset to the right.
/// Each tile is keyed by its entity id so the drawn tile bounces in while existing
/// tiles stay in place; if a tile leaves the hand (discarded/melded), it fades out.
class HandView extends StatelessWidget {
  final List<TileView> tiles;
  final int? justDrewId;
  final void Function(TileView)? onTapTile;
  final Set<int> highlightIds;
  final double tileWidth;

  const HandView({
    super.key,
    required this.tiles,
    this.justDrewId,
    this.onTapTile,
    this.highlightIds = const {},
    this.tileWidth = 58,
  });

  @override
  Widget build(BuildContext context) {
    const suitOrder = {'m': 0, 'p': 1, 's': 2, 'z': 3, 'f': 4};
    final regular = <TileView>[];
    TileView? drawn;
    for (final t in tiles) {
      if (t.id != null && t.id == justDrewId) {
        drawn = t;
      } else {
        regular.add(t);
      }
    }
    regular.sort((a, b) {
      final sa = suitOrder[a.code[0]] ?? 9;
      final sb = suitOrder[b.code[0]] ?? 9;
      if (sa != sb) return sa - sb;
      final ra = int.parse(a.code.substring(1));
      final rb = int.parse(b.code.substring(1));
      return ra - rb;
    });

    final gap = tileWidth * 0.06;
    return Wrap(
      spacing: gap,
      children: [
        for (final t in regular)
          TileFace(
            key: t.id != null ? ValueKey('h-${t.id}') : null,
            tile: t,
            width: tileWidth,
            highlighted: t.id != null && highlightIds.contains(t.id),
            onTap: onTapTile == null ? null : () => onTapTile!(t),
          ),
        if (drawn != null) ...[
          SizedBox(width: tileWidth * 0.4),
          AnimatedTileEntry(
            key: ValueKey('h-drew-${drawn.id}'),
            tile: drawn,
            width: tileWidth,
            highlighted: highlightIds.contains(drawn.id),
            entry: TileEntryAnim.bounce,
            duration: const Duration(milliseconds: 380),
            onTap: onTapTile == null ? null : () => onTapTile!(drawn!),
          ),
        ],
      ],
    );
  }
}
