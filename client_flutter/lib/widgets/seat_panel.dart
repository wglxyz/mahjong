import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../protocol/messages.dart';
import '../theme.dart';
import 'meld_view.dart' as widgets;

/// Compact panel showing a seat's name, points, wind, riichi state, hand count.
/// When [isActive] pulses with a soft gold breathing glow.
/// Points use a ticker (TweenAnimationBuilder<int>) on change.
class SeatPanel extends StatefulWidget {
  final SeatView seat;
  final bool isYou;
  final bool isActive;
  final bool isDealer;
  final int seatWind;   // 1=E, 2=S, 3=W, 4=N (this seat's wind)

  const SeatPanel({
    super.key,
    required this.seat,
    required this.isYou,
    required this.isActive,
    required this.isDealer,
    required this.seatWind,
  });

  static const _winds = ['', '東', '南', '西', '北'];

  @override
  State<SeatPanel> createState() => _SeatPanelState();
}

class _SeatPanelState extends State<SeatPanel> with SingleTickerProviderStateMixin {
  late final AnimationController _pulse = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1700),
  );

  int _prevPoints = 0;

  @override
  void initState() {
    super.initState();
    _prevPoints = widget.seat.points;
    if (widget.isActive) _pulse.repeat(reverse: true);
  }

  @override
  void didUpdateWidget(SeatPanel old) {
    super.didUpdateWidget(old);
    if (widget.isActive && !_pulse.isAnimating) _pulse.repeat(reverse: true);
    if (!widget.isActive && _pulse.isAnimating) {
      _pulse.stop();
      _pulse.value = 0;
    }
    if (old.seat.points != widget.seat.points) {
      _prevPoints = old.seat.points;
    }
  }

  @override
  void dispose() {
    _pulse.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _pulse,
      builder: (ctx, child) {
        // breathing curve: 0..1..0
        final intensity = widget.isActive
            ? (math.sin(_pulse.value * math.pi) * 0.7 + 0.3)
            : 0.0;
        return Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          decoration: BoxDecoration(
            color: AppColors.surfaceRaised,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: widget.isActive
                  ? Color.lerp(AppColors.goldDim, AppColors.goldBright, intensity)!
                  : AppColors.goldDim.withValues(alpha: 0.55),
              width: widget.isActive ? 2 : 1,
            ),
            boxShadow: widget.isActive
                ? [
                    BoxShadow(
                      color: AppColors.gold.withValues(alpha: 0.25 + 0.35 * intensity),
                      blurRadius: 12 + 14 * intensity,
                      spreadRadius: 1 + intensity,
                    ),
                  ]
                : null,
          ),
          child: child,
        );
      },
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 26,
                height: 26,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: widget.isDealer ? AppColors.gold : AppColors.tableEdge,
                ),
                child: Text(
                  SeatPanel._winds[widget.seatWind],
                  style: TextStyle(
                    fontWeight: FontWeight.w700,
                    fontSize: 16,
                    color: widget.isDealer ? AppColors.surface : AppColors.goldBright,
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Text(
                widget.isYou ? '你' : widget.seat.name,
                style: TextStyle(
                  color: widget.isYou ? AppColors.goldBright : AppColors.textPrimary,
                  fontWeight: FontWeight.w700,
                ),
              ),
              if (widget.seat.riichi) ...[
                const SizedBox(width: 6),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                  decoration: BoxDecoration(
                    color: AppColors.riichi.withValues(alpha: 0.85),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: const Text(
                    'リーチ',
                    style: TextStyle(
                      color: AppColors.surface,
                      fontSize: 11,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
              ],
            ],
          ),
          const SizedBox(height: 4),
          TweenAnimationBuilder<int>(
            tween: IntTween(begin: _prevPoints, end: widget.seat.points),
            duration: const Duration(milliseconds: 600),
            curve: Curves.easeOutCubic,
            builder: (ctx, val, _) => Text(
              val.toString(),
              style: const TextStyle(
                color: AppColors.textPrimary,
                fontFeatures: [FontFeature.tabularFigures()],
                fontSize: 18,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
          if (widget.seat.melds.isNotEmpty) ...[
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final m in widget.seat.melds)
                  widgets.MeldView(
                    key: ValueKey('m-${widget.seat.seat}-${m.tiles.map((t) => t.id ?? t.code).join(",")}'),
                    meld: m,
                    ownerSeat: widget.seat.seat,
                    tileWidth: 26,
                  ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}
