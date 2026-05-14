# Avid Mahjong — Flutter Client

Native client for the Avid Python mahjong engine. Connects over WebSocket; backend
is the source of truth for all rules — this app only renders + sends action ids back.

## Quick start

```bash
# 1) start the Python server (from the project root, not this folder)
cd ..
python -m server.server --ruleset riichi --port 8765

# 2) in another shell, run the Flutter client
cd client_flutter
flutter pub get
flutter run -d macos        # or: -d chrome / -d ios / -d android
```

When prompted, the default URL `ws://localhost:8765` works for local testing.
For mobile devices on the same Wi-Fi, point the URL at your machine's LAN IP
(e.g. `ws://192.168.1.50:8765`) and start the server with `--host 0.0.0.0`.

## Project structure

```
assets/tiles/      # placeholder SVG tile set — replace for real artwork
lib/
  main.dart        # app entry, ChangeNotifierProvider<GameState>
  theme.dart       # palette + ThemeData
  protocol/
    messages.dart  # DTOs mirroring server/protocol.py
  services/
    ws_client.dart # WebSocket wrapper
  state/
    game_state.dart # ChangeNotifier; latest snapshot/decision/result
  widgets/
    tile.dart      # single tile (loads SVG asset by code)
    hand_view.dart # your hand + just-drawn tile
    discard_grid.dart
    meld_view.dart # rotates called tile to indicate caller direction
    seat_panel.dart # name + points + wind + riichi badge
    table_view.dart # 4-seat layout (you bottom, others rotated)
    action_bar.dart # decision UI
    win_overlay.dart # end-of-hand modal with yaku
  screens/
    connect_screen.dart
    game_screen.dart
```

## Swapping in real tile artwork

Replace files in `assets/tiles/` with the same names:

```
m1.svg .. m9.svg, m5r.svg (red 5)
p1.svg .. p9.svg, p5r.svg
s1.svg .. s9.svg, s5r.svg
z1.svg (E)  z2 (S)  z3 (W)  z4 (N)
z5 (白)     z6 (發)  z7 (中)
back.svg
```

The Flutter side does **not** need any code change — `TileFace` looks up the
asset by `TileView.assetPath`. PNG works too if you change the SvgPicture call
in `widgets/tile.dart` (or add a fallback).

## Build targets

- **macOS**: `flutter run -d macos` (after `flutter config --enable-macos-desktop`)
- **iOS**: open `ios/Runner.xcworkspace` in Xcode, set team / bundle id, run.
- **Android**: connect a device / start emulator, `flutter run -d android`.
- **Web** (for debugging convenience): `flutter run -d chrome`.

## Re-generating placeholder tiles

If you tweak `scripts/gen_tiles.py` in the project root:

```bash
cd ..
python scripts/gen_tiles.py
```

The script overwrites the files under `client_flutter/assets/tiles/`.
