import 'package:flutter/material.dart';

import '../protocol/messages.dart';
import '../theme.dart';
import 'tile.dart';

/// Bottom bar of buttons for the current decision. Primary actions (TSUMO/RON/
/// RIICHI/PASS) are shown as labelled pills; discards are shown as tappable tile
/// glyphs so the user picks visually.
class ActionBar extends StatelessWidget {
  final List<ActionView> actions;
  final void Function(ActionView) onChoose;

  const ActionBar({super.key, required this.actions, required this.onChoose});

  @override
  Widget build(BuildContext context) {
    if (actions.isEmpty) return const SizedBox.shrink();

    final discards = <ActionView>[];
    final calls = <ActionView>[];          // chi/pon/kan
    final wins = <ActionView>[];           // tsumo/ron
    final riichis = <ActionView>[];
    ActionView? passAction;

    for (final a in actions) {
      switch (a.kind) {
        case 'discard':
          discards.add(a);
          break;
        case 'pass':
          passAction = a;
          break;
        case 'chi':
        case 'pon':
        case 'kan':
          calls.add(a);
          break;
        case 'tsumo':
        case 'ron':
          wins.add(a);
          break;
        case 'riichi':
          riichis.add(a);
          break;
      }
    }

    return Container(
      padding: const EdgeInsets.fromLTRB(20, 12, 20, 16),
      decoration: BoxDecoration(
        color: AppColors.surface.withValues(alpha: 0.92),
        borderRadius: const BorderRadius.vertical(top: Radius.circular(16)),
        border: const Border(
          top: BorderSide(color: AppColors.goldDim, width: 1),
        ),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (wins.isNotEmpty || riichis.isNotEmpty || calls.isNotEmpty || passAction != null) ...[
            Wrap(
              spacing: 10,
              runSpacing: 8,
              children: [
                for (final w in wins)
                  _primaryButton(
                    label: w.kind == 'tsumo' ? 'TSUMO  自摸' : 'RON  荣和',
                    color: w.kind == 'tsumo' ? AppColors.tsumo : AppColors.ron,
                    onTap: () => onChoose(w),
                  ),
                for (final r in riichis)
                  _primaryButton(
                    label: 'RIICHI  立直',
                    subtitle: r.tiles.isNotEmpty ? '弃 ${r.tiles.first.code}' : null,
                    color: AppColors.riichi,
                    onTap: () => onChoose(r),
                  ),
                for (final c in calls)
                  _secondaryButton(
                    label: c.kind.toUpperCase(),
                    extra: c.extra['kan_kind'] as String?,
                    onTap: () => onChoose(c),
                  ),
                if (passAction != null)
                  OutlinedButton(
                    onPressed: () => onChoose(passAction!),
                    child: const Text('PASS  跳过'),
                  ),
              ],
            ),
            if (discards.isNotEmpty) const SizedBox(height: 12),
          ],
          if (discards.isNotEmpty)
            Row(
              children: [
                const Text(
                  '打：',
                  style: TextStyle(color: AppColors.textSecondary, fontSize: 13),
                ),
                const SizedBox(width: 6),
                Expanded(
                  child: SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: Row(
                      children: [
                        for (final d in discards)
                          Padding(
                            padding: const EdgeInsets.only(right: 6),
                            child: GestureDetector(
                              onTap: () => onChoose(d),
                              child: AnimatedScale(
                                scale: 1.0,
                                duration: const Duration(milliseconds: 200),
                                child: TileFace(
                                  tile: d.tiles.isNotEmpty ? d.tiles.first : null,
                                  width: 40,
                                ),
                              ),
                            ),
                          ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
        ],
      ),
    );
  }

  Widget _primaryButton({
    required String label,
    String? subtitle,
    required Color color,
    required VoidCallback onTap,
  }) {
    return Material(
      color: color,
      shape: const StadiumBorder(),
      elevation: 4,
      shadowColor: color.withValues(alpha: 0.7),
      child: InkWell(
        customBorder: const StadiumBorder(),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 10),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                label,
                style: const TextStyle(
                  color: AppColors.surface,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 1.2,
                ),
              ),
              if (subtitle != null)
                Text(
                  subtitle,
                  style: TextStyle(
                    color: AppColors.surface.withValues(alpha: 0.8),
                    fontSize: 11,
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _secondaryButton({required String label, String? extra, required VoidCallback onTap}) {
    return OutlinedButton(
      onPressed: onTap,
      child: Text(extra != null ? '$label  ($extra)' : label),
    );
  }
}
