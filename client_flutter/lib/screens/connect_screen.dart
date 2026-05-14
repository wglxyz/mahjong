import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../state/game_state.dart';
import '../theme.dart';

class ConnectScreen extends StatefulWidget {
  const ConnectScreen({super.key});

  @override
  State<ConnectScreen> createState() => _ConnectScreenState();
}

class _ConnectScreenState extends State<ConnectScreen> {
  late final TextEditingController _ctl;

  @override
  void initState() {
    super.initState();
    final gs = context.read<GameState>();
    _ctl = TextEditingController(text: gs.hostUrl);
  }

  @override
  void dispose() {
    _ctl.dispose();
    super.dispose();
  }

  Future<void> _connect() async {
    final gs = context.read<GameState>();
    gs.hostUrl = _ctl.text.trim();
    await gs.connect();
    if (gs.status == ConnectionStatus.connected && mounted) {
      Navigator.of(context).pushReplacementNamed('/game');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.tableFelt,
      body: Center(
        child: Container(
          constraints: const BoxConstraints(maxWidth: 460),
          padding: const EdgeInsets.all(32),
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: AppColors.gold, width: 1.2),
            boxShadow: [
              BoxShadow(
                color: AppColors.gold.withValues(alpha: 0.25),
                blurRadius: 30,
                spreadRadius: 2,
              ),
            ],
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text(
                'AVID 麻 雀',
                style: TextStyle(
                  color: AppColors.goldBright,
                  fontSize: 32,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 10,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 8),
              const Text(
                'connect to your engine',
                style: TextStyle(
                  color: AppColors.textSecondary,
                  letterSpacing: 3,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 32),
              TextField(
                controller: _ctl,
                decoration: const InputDecoration(
                  labelText: 'WebSocket URL',
                  hintText: 'ws://localhost:8765',
                ),
                style: const TextStyle(fontFamily: 'monospace'),
                onSubmitted: (_) => _connect(),
              ),
              const SizedBox(height: 24),
              Consumer<GameState>(
                builder: (ctx, gs, _) => Column(
                  children: [
                    if (gs.errorMessage != null)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 12),
                        child: Text(
                          gs.errorMessage!,
                          style: const TextStyle(color: AppColors.danger),
                          textAlign: TextAlign.center,
                        ),
                      ),
                    ElevatedButton(
                      onPressed: gs.status == ConnectionStatus.connecting ? null : _connect,
                      child: gs.status == ConnectionStatus.connecting
                          ? const SizedBox(
                              height: 18,
                              width: 18,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Text('入  局'),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
