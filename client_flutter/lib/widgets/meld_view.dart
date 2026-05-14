import 'package:flutter/material.dart';

import '../protocol/messages.dart';
import 'animated_tile.dart';
import 'tile.dart';

/// Render a single meld: tiles in a row, with the called tile rotated sideways
/// based on which opponent it came from. Whole meld scale-fades in on first build.
class MeldView extends StatefulWidget {
  final dynamic meld;  // protocol.MeldView; dynamic to avoid name shadow with this class
  final int ownerSeat;
  final double tileWidth;

  const MeldView({
    super.key,
    required this.meld,
    required this.ownerSeat,
    this.tileWidth = 32,
  });

  @override
  State<MeldView> createState() => _MeldViewState();
}

class _MeldViewState extends State<MeldView>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 380),
  )..forward();
  late final Animation<double> _t =
      CurvedAnimation(parent: _ctrl, curve: Curves.easeOutBack);

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final List<TileView> tiles = widget.meld.tiles;
    final String type = widget.meld.meldType;
    final int? from = widget.meld.calledFrom;

    final isAnkan = type == 'ankan';

    int rotatedIndex = -1;
    if (from != null && !isAnkan) {
      final rel = (from - widget.ownerSeat) % 4;
      if (rel == 3) rotatedIndex = 0;
      if (rel == 2) rotatedIndex = 1;
      if (rel == 1) rotatedIndex = tiles.length - 1;
    }

    final widgets = <Widget>[];
    for (var i = 0; i < tiles.length; i++) {
      final t = tiles[i];
      final isMiddleAnkanFaceDown = isAnkan && (i == 1 || i == 2);
      widgets.add(TileFace(
        tile: isMiddleAnkanFaceDown ? null : t,
        width: widget.tileWidth,
        rotation: (i == rotatedIndex) ? 0.25 : 0,
      ));
      if (i < tiles.length - 1) {
        widgets.add(SizedBox(width: widget.tileWidth * 0.08));
      }
    }

    return AnimatedBuilder(
      animation: _t,
      builder: (_, child) => Transform.scale(
        scale: 0.55 + 0.45 * _t.value,
        alignment: Alignment.bottomCenter,
        child: Opacity(opacity: _t.value.clamp(0.0, 1.0), child: child),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: widgets,
      ),
    );
  }
}
