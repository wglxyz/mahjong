import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../protocol/messages.dart';
import '../theme.dart';

/// Modal-style overlay shown when a hand ends. Stages:
///   0–400ms: background fade + card scale-in
///   400ms onwards: yaku rows slide+fade in one at a time
///   continuously: rotating gold halo behind the card
class WinOverlay extends StatefulWidget {
  final HandEnded result;
  final List<String> seatNames;
  final VoidCallback onDismiss;

  const WinOverlay({
    super.key,
    required this.result,
    required this.seatNames,
    required this.onDismiss,
  });

  @override
  State<WinOverlay> createState() => _WinOverlayState();
}

class _WinOverlayState extends State<WinOverlay>
    with TickerProviderStateMixin {
  late final AnimationController _intro = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 520),
  )..forward();
  late final AnimationController _halo = AnimationController(
    vsync: this,
    duration: const Duration(seconds: 14),
  )..repeat();
  late final AnimationController _yakuTimer = AnimationController(
    vsync: this,
    duration: Duration(milliseconds: 600 + 100 * (widget.result.yaku.length + 1)),
  )..forward();

  late final Animation<double> _fade =
      CurvedAnimation(parent: _intro, curve: const Interval(0, 0.4));
  late final Animation<double> _scale =
      CurvedAnimation(parent: _intro, curve: Curves.easeOutBack);

  @override
  void dispose() {
    _intro.dispose();
    _halo.dispose();
    _yakuTimer.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final r = widget.result;
    final isWin = r.result == 'win';
    return Stack(
      children: [
        FadeTransition(
          opacity: _fade,
          child: Container(color: Colors.black.withValues(alpha: 0.72)),
        ),
        if (isWin) _GoldHalo(controller: _halo),
        Center(
          child: ScaleTransition(
            scale: Tween<double>(begin: 0.6, end: 1).animate(_scale),
            child: FadeTransition(
              opacity: _fade,
              child: Container(
                constraints: const BoxConstraints(maxWidth: 480),
                padding: const EdgeInsets.fromLTRB(28, 24, 28, 20),
                decoration: BoxDecoration(
                  color: AppColors.surfaceRaised,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: AppColors.gold, width: 1.5),
                  boxShadow: [
                    BoxShadow(
                      color: AppColors.gold.withValues(alpha: 0.55),
                      blurRadius: 50,
                      spreadRadius: 4,
                    ),
                  ],
                ),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      isWin ? '和 牌' : '流 局',
                      style: const TextStyle(
                        color: AppColors.goldBright,
                        fontSize: 36,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 8,
                      ),
                    ),
                    const SizedBox(height: 16),
                    if (isWin) ...[
                      Text(
                        r.loser == null
                            ? '${_name(r.winner!)} 自摸'
                            : '${_name(r.winner!)} 荣和 ${_name(r.loser!)}',
                        style: const TextStyle(color: AppColors.textPrimary, fontSize: 18),
                      ),
                      const SizedBox(height: 18),
                      if (r.han != null && r.fu != null)
                        Text(
                          '${r.han} 番 / ${r.fu} 符',
                          style: const TextStyle(
                            color: AppColors.textSecondary,
                            fontSize: 14,
                            letterSpacing: 2,
                          ),
                        ),
                      const SizedBox(height: 6),
                      TweenAnimationBuilder<int>(
                        duration: const Duration(milliseconds: 900),
                        curve: Curves.easeOutCubic,
                        tween: IntTween(begin: 0, end: r.score),
                        builder: (ctx, val, _) => Text(
                          '+$val',
                          style: const TextStyle(
                            color: AppColors.goldBright,
                            fontSize: 42,
                            fontWeight: FontWeight.w900,
                            fontFeatures: [FontFeature.tabularFigures()],
                          ),
                        ),
                      ),
                      if (r.yaku.isNotEmpty) ...[
                        const SizedBox(height: 12),
                        const Divider(color: AppColors.goldDim, height: 1),
                        const SizedBox(height: 12),
                        for (var i = 0; i < r.yaku.length; i++)
                          _YakuRow(
                            name: r.yaku[i].key,
                            value: r.yaku[i].value,
                            delay: 600 + i * 100,
                            timer: _yakuTimer,
                          ),
                      ],
                    ] else ...[
                      const SizedBox(height: 8),
                      const Text(
                        '本场流局，无人胡牌',
                        style: TextStyle(color: AppColors.textSecondary, fontSize: 14),
                      ),
                    ],
                    const SizedBox(height: 22),
                    ElevatedButton(onPressed: widget.onDismiss, child: const Text('关闭')),
                  ],
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }

  String _name(int seat) {
    if (seat >= 0 && seat < widget.seatNames.length) return widget.seatNames[seat];
    return 'P$seat';
  }
}

class _YakuRow extends StatelessWidget {
  final String name;
  final int value;
  final int delay;
  final AnimationController timer;

  const _YakuRow({
    required this.name,
    required this.value,
    required this.delay,
    required this.timer,
  });

  @override
  Widget build(BuildContext context) {
    final total = timer.duration!.inMilliseconds;
    final start = (delay / total).clamp(0.0, 1.0);
    final end = ((delay + 320) / total).clamp(0.0, 1.0);
    return AnimatedBuilder(
      animation: timer,
      builder: (ctx, _) {
        final raw = ((timer.value - start) / (end - start)).clamp(0.0, 1.0);
        final t = Curves.easeOutCubic.transform(raw);
        return Opacity(
          opacity: t,
          child: Transform.translate(
            offset: Offset(0, (1 - t) * 8),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 2),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(name, style: const TextStyle(color: AppColors.textPrimary, fontSize: 15)),
                  const SizedBox(width: 14),
                  Text(
                    value >= 13 ? '役満' : '$value 番',
                    style: const TextStyle(
                      color: AppColors.goldBright,
                      fontSize: 14,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}

/// Slowly-rotating soft halo behind the card, for celebratory flair.
class _GoldHalo extends StatelessWidget {
  final AnimationController controller;
  const _GoldHalo({required this.controller});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: AnimatedBuilder(
        animation: controller,
        builder: (ctx, _) {
          return Transform.rotate(
            angle: controller.value * 2 * math.pi,
            child: Container(
              width: 700,
              height: 700,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: SweepGradient(
                  colors: [
                    AppColors.gold.withValues(alpha: 0.0),
                    AppColors.goldBright.withValues(alpha: 0.18),
                    AppColors.gold.withValues(alpha: 0.0),
                    AppColors.goldBright.withValues(alpha: 0.12),
                    AppColors.gold.withValues(alpha: 0.0),
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}
