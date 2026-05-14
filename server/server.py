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
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed

from server.protocol import DecideMsg
from server.session import Session


log = logging.getLogger("avid.server")


class App:
    def __init__(self, ruleset_name: str, seed: int | None = None) -> None:
        self.ruleset_name = ruleset_name
        self.seed = seed

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
                except (asyncio.TimeoutError, asyncio.CancelledError):
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
        async with websockets.serve(app.handle, args.host, args.port):
            log.info("server listening on ws://%s:%d  (ruleset=%s)", args.host, args.port, args.ruleset)
            await asyncio.Future()  # run forever

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        log.info("server stopped by KeyboardInterrupt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
