import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../protocol/messages.dart';
import '../state/game_state.dart';
import '../theme.dart';
import '../widgets/action_bar.dart';
import '../widgets/table_view.dart';
import '../widgets/win_overlay.dart';

class GameScreen extends StatefulWidget {
  const GameScreen({super.key});

  @override
  State<GameScreen> createState() => _GameScreenState();
}

class _GameScreenState extends State<GameScreen> {
  bool _dismissedResult = false;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Consumer<GameState>(
          builder: (ctx, gs, _) {
            if (gs.status != ConnectionStatus.connected) {
              return Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const CircularProgressIndicator(),
                    const SizedBox(height: 16),
                    if (gs.errorMessage != null)
                      Text(
                        gs.errorMessage!,
                        style: const TextStyle(color: AppColors.danger),
                      ),
                  ],
                ),
              );
            }
            if (gs.snapshot == null) {
              return const Center(
                child: Text(
                  '等待发牌…',
                  style: TextStyle(color: AppColors.textSecondary, letterSpacing: 4),
                ),
              );
            }
            final snap = gs.snapshot!;
            final youSeatNames = gs.welcome?.seats ?? const ['E', 'S', 'W', 'N'];

            // map action id to discard tile id, so user can tap a hand tile to discard
            final discardByTileId = <int, ActionView>{};
            for (final a in gs.pendingActions ?? const <ActionView>[]) {
              if (a.kind == 'discard' && a.tiles.isNotEmpty && a.tiles.first.id != null) {
                discardByTileId[a.tiles.first.id!] = a;
              }
            }
            final highlight = discardByTileId.keys.toSet();

            return Stack(
              children: [
                Column(
                  children: [
                    Expanded(
                      child: TableView(
                        snap: snap,
                        highlightHandIds: highlight,
                        onTapMyTile: (t) {
                          if (t.id != null && discardByTileId.containsKey(t.id)) {
                            gs.decide(discardByTileId[t.id]!.id);
                          }
                        },
                      ),
                    ),
                    if (gs.awaitingDecision)
                      ActionBar(
                        actions: gs.pendingActions!,
                        onChoose: (a) => gs.decide(a.id),
                      ),
                  ],
                ),
                Positioned(
                  top: 12,
                  right: 12,
                  child: _ConnectionBadge(status: gs.status, onDisconnect: () async {
                    await gs.disconnect();
                    if (mounted) Navigator.of(context).pushReplacementNamed('/');
                  }),
                ),
                if (gs.handResult != null && !_dismissedResult)
                  WinOverlay(
                    result: gs.handResult!,
                    seatNames: youSeatNames,
                    onDismiss: () => setState(() => _dismissedResult = true),
                  ),
              ],
            );
          },
        ),
      ),
    );
  }
}

class _ConnectionBadge extends StatelessWidget {
  final ConnectionStatus status;
  final VoidCallback onDisconnect;

  const _ConnectionBadge({required this.status, required this.onDisconnect});

  @override
  Widget build(BuildContext context) {
    final color = status == ConnectionStatus.connected
        ? AppColors.gold
        : AppColors.danger;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: AppColors.surface.withValues(alpha: 0.7),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withValues(alpha: 0.6)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
          const SizedBox(width: 8),
          TextButton(
            style: TextButton.styleFrom(
              padding: EdgeInsets.zero,
              minimumSize: const Size(0, 0),
              foregroundColor: AppColors.textPrimary,
              textStyle: const TextStyle(fontSize: 12),
            ),
            onPressed: onDisconnect,
            child: const Text('退出'),
          ),
        ],
      ),
    );
  }
}
