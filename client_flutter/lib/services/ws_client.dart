import 'dart:async';
import 'dart:convert';

import 'package:web_socket_channel/status.dart' as ws_status;
import 'package:web_socket_channel/web_socket_channel.dart';

/// Thin wrapper over web_socket_channel. Hands raw decoded JSON maps up to the
/// caller; doesn't know anything about specific message types.
class WsClient {
  WebSocketChannel? _channel;
  StreamController<Map<String, dynamic>>? _msgs;
  StreamSubscription? _sub;

  Stream<Map<String, dynamic>> get messages =>
      _msgs?.stream ?? const Stream.empty();
  bool get isConnected => _channel != null;

  Future<void> connect(String url) async {
    if (_channel != null) {
      await close();
    }
    final ch = WebSocketChannel.connect(Uri.parse(url));
    await ch.ready;
    _channel = ch;
    _msgs = StreamController<Map<String, dynamic>>.broadcast();
    _sub = ch.stream.listen(
      (data) {
        final raw = data is String ? data : utf8.decode(data as List<int>);
        try {
          final m = jsonDecode(raw);
          if (m is Map<String, dynamic>) _msgs!.add(m);
        } on FormatException {
          // skip malformed frames
        }
      },
      onDone: () {
        _msgs?.close();
        _channel = null;
      },
      onError: (e) {
        _msgs?.addError(e);
      },
    );
  }

  void send(Map<String, dynamic> msg) {
    _channel?.sink.add(jsonEncode(msg));
  }

  void decide(String actionId) => send({'type': 'decide', 'action_id': actionId});
  void requestSnapshot() => send({'type': 'request_snapshot'});

  Future<void> close() async {
    await _sub?.cancel();
    await _channel?.sink.close(ws_status.normalClosure);
    _channel = null;
    await _msgs?.close();
    _msgs = null;
  }
}
