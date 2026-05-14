import 'package:flutter/material.dart';

import '../protocol/messages.dart';
import 'animated_tile.dart';

/// 6-wide pyramid of discards in front of a seat. New tiles slide in from above.
///
/// We key each tile by its entity id so Flutter reuses State for tiles that
/// stayed in place. Newly-appended tiles get fresh State → fresh animation.
class DiscardGrid extends StatelessWidget {
  final List<TileView> discards;
  final double rotation;
  final double tileWidth;
  final int columns;

  const DiscardGrid({
    super.key,
    required this.discards,
    this.rotation = 0,
    this.tileWidth = 34,
    this.columns = 6,
  });

  @override
  Widget build(BuildContext context) {
    final rows = <Widget>[];
    final gap = tileWidth * 0.10;
    for (var i = 0; i < discards.length; i += columns) {
      final slice = discards.sublist(i, (i + columns).clamp(0, discards.length));
      rows.add(
        Padding(
          padding: EdgeInsets.only(top: i == 0 ? 0 : gap),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              for (var k = 0; k < slice.length; k++)
                Padding(
                  padding: EdgeInsets.only(left: k == 0 ? 0 : gap),
                  child: AnimatedTileEntry(
                    key: slice[k].id != null
                        ? ValueKey('disc-${slice[k].id}')
                        : null,
                    tile: slice[k],
                    width: tileWidth,
                  ),
                ),
            ],
          ),
        ),
      );
    }

    Widget grid = Column(mainAxisSize: MainAxisSize.min, children: rows);
    if (rotation != 0) {
      grid = RotatedBox(quarterTurns: (rotation * 4).round(), child: grid);
    }
    return grid;
  }
}
