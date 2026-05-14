import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'screens/connect_screen.dart';
import 'screens/game_screen.dart';
import 'state/game_state.dart';
import 'theme.dart';

void main() {
  runApp(
    ChangeNotifierProvider(
      create: (_) => GameState(),
      child: const AvidMahjongApp(),
    ),
  );
}

class AvidMahjongApp extends StatelessWidget {
  const AvidMahjongApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Avid Mahjong',
      theme: buildTheme(),
      debugShowCheckedModeBanner: false,
      routes: {
        '/': (_) => const ConnectScreen(),
        '/game': (_) => const GameScreen(),
      },
      initialRoute: '/',
    );
  }
}
