import 'dart:async';

import 'package:flutter/foundation.dart';

import '../protocol/messages.dart';
import '../services/ws_client.dart';

/// Holds the latest snapshot + pending decision + recent event for the UI to render.
/// Subscribes to a WsClient and routes inbound messages.
class GameState extends ChangeNotifier {
  final WsClient _client = WsClient();
  StreamSubscription<Map<String, dynamic>>? _sub;

  ConnectionStatus status = ConnectionStatus.disconnected;
  String? errorMessage;

  Welcome? welcome;
  Snapshot? snapshot;
  List<ActionView>? pendingActions;
  HandEnded? handResult;
  MatchEnded? matchResult;

  /// Latest event (for animations / banners). UI may consume it.
  GameEvent? lastEvent;

  String get hostUrl => _hostUrl;
  String _hostUrl = 'ws://127.0.0.1:8765';
  set hostUrl(String v) {
    _hostUrl = v;
    notifyListeners();
  }

  bool get awaitingDecision => pendingActions != null && pendingActions!.isNotEmpty;
  bool get isMyTurn => awaitingDecision;
  int? get yourSeat => welcome?.yourSeat ?? snapshot?.yourSeat;

  Future<void> connect() async {
    status = ConnectionStatus.connecting;
    errorMessage = null;
    notifyListeners();
    try {
      await _client.connect(_hostUrl);
      _sub = _client.messages.listen(_onMessage, onError: _onError);
      status = ConnectionStatus.connected;
    } catch (e) {
      status = ConnectionStatus.disconnected;
      errorMessage = e.toString();
    }
    notifyListeners();
  }

  Future<void> disconnect() async {
    await _sub?.cancel();
    _sub = null;
    await _client.close();
    status = ConnectionStatus.disconnected;
    welcome = null;
    snapshot = null;
    pendingActions = null;
    handResult = null;
    matchResult = null;
    notifyListeners();
  }

  void decide(String actionId) {
    if (!awaitingDecision) return;
    _client.decide(actionId);
    pendingActions = null;
    notifyListeners();
  }

  void requestSnapshot() => _client.requestSnapshot();

  // ---- inbound handling -------------------------------------------------
  void _onMessage(Map<String, dynamic> msg) {
    final t = msg['type'] as String?;
    switch (t) {
      case 'welcome':
        welcome = Welcome.fromJson(msg);
        break;
      case 'snapshot':
        snapshot = Snapshot.fromJson(msg);
        break;
      case 'decision':
        pendingActions = (msg['actions'] as List)
            .map((a) => ActionView.fromJson(a as Map<String, dynamic>))
            .toList();
        break;
      case 'event':
        lastEvent = GameEvent.fromJson(msg);
        break;
      case 'hand_ended':
        handResult = HandEnded.fromJson(msg);
        pendingActions = null;
        break;
      case 'match_ended':
        matchResult = MatchEnded.fromJson(msg);
        pendingActions = null;
        break;
      case 'error':
        errorMessage = msg['error'] as String?;
        break;
    }
    notifyListeners();
  }

  void _onError(Object e) {
    errorMessage = e.toString();
    status = ConnectionStatus.disconnected;
    notifyListeners();
  }

  @override
  void dispose() {
    _sub?.cancel();
    _client.close();
    super.dispose();
  }
}

enum ConnectionStatus { disconnected, connecting, connected }
