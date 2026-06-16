"""WebSocket entry point.

Usage:
    python -m server.server --ruleset riichi --port 8765

Each client connection gets its own Session (1 game). On disconnect the session is
torn down. Engine runs in a background thread; this asyncio task mediates the WS.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

import websockets
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response

from server.protocol import DecideMsg
from server.session import Session

log = logging.getLogger("avid.server")

# Static web client served over HTTP on the same port as the WS endpoint, so a
# remote browser can just open http://<host>:<port>/ — no separate file server,
# and the page connects its WebSocket back to the same host:port.
WEB_ROOT = Path(__file__).resolve().parent.parent / "client_web"
WEB_INDEX = WEB_ROOT / "index.html"

_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".svg": "image/svg+xml",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".png": "image/png",
}


class App:
    def __init__(self, ruleset_name: str, seed: int | None = None) -> None:
        self.ruleset_name = ruleset_name
        self.seed = seed

    def serve_http(self, connection, request: Request) -> Response | None:
        """Serve the web client for plain HTTP GETs; let WebSocket upgrades pass through.

        Called by `websockets.serve(process_request=...)` for every incoming request.
        Returning None proceeds with the WS handshake; returning a Response short-circuits
        with a normal HTTP reply (used to hand the browser the static page)."""
        if (request.headers.get("Upgrade") or "").lower() == "websocket":
            return None  # real WS client — proceed to handshake → handle()

        # map URL path → file under client_web/ (index.html for "/"); guard traversal
        raw_path = (request.path or "/").split("?", 1)[0]
        rel = raw_path.lstrip("/") or "index.html"
        target = (WEB_ROOT / rel).resolve()
        if not str(target).startswith(str(WEB_ROOT)) or not target.is_file():
            return connection.respond(404, "not found\n")

        body = target.read_bytes()
        headers = Headers()
        headers["Content-Type"] = _CONTENT_TYPES.get(target.suffix, "application/octet-stream")
        headers["Content-Length"] = str(len(body))
        if target.suffix == ".svg":  # tiles are immutable — let the browser cache them
            headers["Cache-Control"] = "public, max-age=86400"
        return Response(200, "OK", headers, body)

    async def handle(self, ws) -> None:
        peer = ws.remote_address
        log.info("client connected: %s", peer)
        session = Session(ruleset_name=self.ruleset_name, human_seat=0, seed=self.seed)
        outbox_task: asyncio.Task | None = None
        try:
            await ws.send(json.dumps(session.welcome_message()))
            session.start()
            outbox_task = asyncio.create_task(self._outbox_pump(ws, session))
            try:
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        await ws.send(json.dumps({"type": "error", "error": "invalid json"}))
                        continue
                    await self._handle_client_msg(ws, session, msg)
            except ConnectionClosed:
                pass
        finally:
            session.close()
            # post a sentinel so the executor-thread blocked in outbox.get() wakes up
            session.outbox.put({"type": "_terminate"})
            if outbox_task is not None:
                try:
                    await asyncio.wait_for(outbox_task, timeout=2)
                except (TimeoutError, asyncio.CancelledError):
                    outbox_task.cancel()
            log.info("client disconnected: %s", peer)

    async def _handle_client_msg(self, ws, session: Session, msg: dict) -> None:
        kind = msg.get("type")
        if kind == "decide":
            try:
                d = DecideMsg.from_dict(msg)
            except KeyError:
                await ws.send(json.dumps({"type": "error", "error": "decide missing action_id"}))
                return
            ok = session.deliver_decision(d.action_id)
            if not ok:
                await ws.send(json.dumps({"type": "error", "error": f"unknown action_id {d.action_id}"}))
        elif kind == "request_snapshot":
            await ws.send(json.dumps(session.initial_snapshot()))
        else:
            await ws.send(json.dumps({"type": "error", "error": f"unknown message type: {kind}"}))

    async def _outbox_pump(self, ws, session: Session) -> None:
        """Forward outgoing messages from the engine thread to the WS."""
        loop = asyncio.get_running_loop()
        while True:
            msg = await loop.run_in_executor(None, session.outbox.get)
            t = msg.get("type")
            if t == "_terminate":
                return
            if t == "_end":
                # engine finished; keep pumping until terminate sentinel
                continue
            try:
                await ws.send(json.dumps(msg))
            except ConnectionClosed:
                return


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--ruleset", choices=("simple", "riichi"), default="riichi")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)

    logging.basicConfig(level=args.log_level)
    app = App(ruleset_name=args.ruleset, seed=args.seed)

    async def run() -> None:
        async with websockets.serve(app.handle, args.host, args.port, process_request=app.serve_http):
            log.info("server listening on ws://%s:%d  (ruleset=%s)", args.host, args.port, args.ruleset)
            log.info("web client: http://%s:%d/", args.host, args.port)
            await asyncio.Future()  # run forever

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        log.info("server stopped by KeyboardInterrupt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
