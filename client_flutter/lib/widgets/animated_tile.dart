import 'package:flutter/material.dart';

import '../protocol/messages.dart';
import 'tile.dart';

/// TileFace that plays a one-shot appear animation the first time it builds.
/// When the tile is replaced (parent rebuilds with the same widget at the same
/// position), the existing State is reused — no re-animation. So new tiles
/// appended at the end of a list naturally animate; existing tiles stay put.
class AnimatedTileEntry extends StatefulWidget {
  final TileView? tile;
  final double width;
  final double rotation;
  final bool highlighted;
  final VoidCallback? onTap;

  /// Entry style. "slide_down" for discards; "scale" for melds & drawn tile.
  final TileEntryAnim entry;
  final Duration duration;

  const AnimatedTileEntry({
    super.key,
    required this.tile,
    this.width = 32,
    this.rotation = 0,
    this.highlighted = false,
    this.onTap,
    this.entry = TileEntryAnim.slideDown,
    this.duration = const Duration(milliseconds: 240),
  });

  @override
  State<AnimatedTileEntry> createState() => _AnimatedTileEntryState();
}

enum TileEntryAnim { slideDown, scale, bounce }

class _AnimatedTileEntryState extends State<AnimatedTileEntry>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  late final Animation<double> _t;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(vsync: this, duration: widget.duration);
    Curve curve;
    switch (widget.entry) {
      case TileEntryAnim.slideDown:
        curve = Curves.easeOutCubic;
        break;
      case TileEntryAnim.scale:
        curve = Curves.easeOutBack;
        break;
      case TileEntryAnim.bounce:
        curve = Curves.elasticOut;
        break;
    }
    _t = CurvedAnimation(parent: _ctrl, curve: curve);
    _ctrl.forward();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _t,
      builder: (ctx, _) {
        final v = _t.value;
        final base = TileFace(
          tile: widget.tile,
          width: widget.width,
          rotation: widget.rotation,
          highlighted: widget.highlighted,
          onTap: widget.onTap,
        );
        switch (widget.entry) {
          case TileEntryAnim.slideDown:
            return Transform.translate(
              offset: Offset(0, (1 - v) * -widget.width * 0.55),
              child: Opacity(opacity: v.clamp(0.0, 1.0), child: base),
            );
          case TileEntryAnim.scale:
            return Transform.scale(
              scale: 0.5 + 0.5 * v,
              child: Opacity(opacity: v.clamp(0.0, 1.0), child: base),
            );
          case TileEntryAnim.bounce:
            return Transform.scale(
              scale: 0.0 + v,
              child: Opacity(opacity: v.clamp(0.0, 1.0), child: base),
            );
        }
      },
    );
  }
}
