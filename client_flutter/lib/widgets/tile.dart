import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';

import '../protocol/messages.dart';
import '../theme.dart';

/// Renders a single tile.
///
///   - [tile] = null → renders the tile back (face-down).
///   - [rotation] in turns (0 .. 1): 0=upright, 0.25=90° CW, 0.5=180°, 0.75=270° CW.
///   - [highlighted] adds an inner glow to mark "just drawn" or "selectable".
///   - [dim] lowers opacity for non-playable tiles.
class TileFace extends StatelessWidget {
  final TileView? tile;
  final double width;
  final double rotation;
  final bool highlighted;
  final bool dim;
  final VoidCallback? onTap;

  const TileFace({
    super.key,
    required this.tile,
    this.width = 44,
    this.rotation = 0,
    this.highlighted = false,
    this.dim = false,
    this.onTap,
  });

  static const double aspectRatio = 100 / 140;

  @override
  Widget build(BuildContext context) {
    final h = width / aspectRatio;
    final asset = tile?.assetPath ?? 'assets/tiles/back.svg';
    Widget face = SizedBox(
      width: width,
      height: h,
      child: SvgPicture.asset(
        asset,
        fit: BoxFit.contain,
      ),
    );

    face = Container(
      width: width,
      height: h,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(width * 0.11),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.45),
            offset: const Offset(0, 2),
            blurRadius: 4,
            spreadRadius: 0,
          ),
          if (highlighted)
            BoxShadow(
              color: AppColors.goldBright.withValues(alpha: 0.75),
              blurRadius: 14,
              spreadRadius: 1,
            ),
        ],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(width * 0.11),
        child: face,
      ),
    );

    if (dim) {
      face = Opacity(opacity: 0.55, child: face);
    }

    if (rotation != 0) {
      face = RotatedBox(quarterTurns: (rotation * 4).round(), child: face);
    }

    if (onTap != null) {
      face = MouseRegion(
        cursor: SystemMouseCursors.click,
        child: GestureDetector(onTap: onTap, child: face),
      );
    }

    return face;
  }
}
