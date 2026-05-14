import 'package:flutter/material.dart';

import '../theme.dart';

/// A horizontal riichi stick (1000-point bar). Slides in from below with a tiny bounce.
/// Displayed below a seat panel when that seat has riichi'd.
class RiichiStick extends StatefulWidget {
  final double width;
  const RiichiStick({super.key, this.width = 110});

  @override
  State<RiichiStick> createState() => _RiichiStickState();
}

class _RiichiStickState extends State<RiichiStick>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 520),
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
    return AnimatedBuilder(
      animation: _t,
      builder: (_, child) => Transform.translate(
        offset: Offset(0, (1 - _t.value) * 18),
        child: Opacity(opacity: _t.value.clamp(0.0, 1.0), child: child),
      ),
      child: Container(
        width: widget.width,
        height: 16,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(8),
          gradient: const LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [Color(0xFFFFF1CB), Color(0xFFE8C079)],
          ),
          border: Border.all(color: AppColors.goldDim, width: 1),
          boxShadow: [
            BoxShadow(
              color: AppColors.riichi.withValues(alpha: 0.7),
              blurRadius: 10,
              spreadRadius: 0.5,
            ),
          ],
        ),
        child: Center(
          child: Container(
            width: 7,
            height: 7,
            decoration: const BoxDecoration(
              shape: BoxShape.circle,
              color: Color(0xFFD42C2C),
            ),
          ),
        ),
      ),
    );
  }
}
