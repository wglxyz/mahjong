"""End-to-end: start server in-process, connect a Python client, auto-decide,
verify the full game flows over the wire."""
from __future__ import annotations

import asyncio
import json
import sys

import websockets

from server.server import App


async def _client(port: int, max_decisions: int = 2000) -> dict:
    """Connect, accept whatever choice index 0 picks, until hand ends."""
    uri = f"ws://127.0.0.1:{port}"
    async with websockets.connect(uri) as ws:
        decisions = 0
        result: dict = {"events": 0, "snapshots": 0, "decisions": 0, "hand_ended": None}
        async for raw in ws:
            msg = json.loads(raw)
            t = msg.get("type")
            if t == "welcome":
                pass
            elif t == "snapshot":
                result["snapshots"] += 1
            elif t == "event":
                result["events"] += 1
            elif t == "decision":
                result["decisions"] += 1
                decisions += 1
                if decisions > max_decisions:
                    break
                # pick the first action
                actions = msg.get("actions", [])
                if not actions:
                    break
                await ws.send(json.dumps({"type": "decide", "action_id": actions[0]["id"]}))
            elif t == "hand_ended":
                result["hand_ended"] = msg
                break
            elif t == "error":
                result["error"] = msg.get("error")
                break
        return result


async def _run(ruleset: str, seed: int, port: int) -> dict:
    app = App(ruleset_name=ruleset, seed=seed)
    server = await websockets.serve(app.handle, "127.0.0.1", port)
    try:
        res = await asyncio.wait_for(_client(port), timeout=60)
    finally:
        server.close()
        await server.wait_closed()
    return res


def test_simple_ruleset_runs_to_hand_end() -> None:
    res = asyncio.run(_run("simple", seed=42, port=8801))
    assert res.get("hand_ended") is not None, f"no hand_ended: {res}"
    assert res["snapshots"] > 0
    assert res["events"] > 0
    assert res["decisions"] > 0


def test_riichi_ruleset_runs_to_hand_end() -> None:
    res = asyncio.run(_run("riichi", seed=1, port=8802))
    assert res.get("hand_ended") is not None, f"no hand_ended: {res}"


if __name__ == "__main__":
    import sys
    mod = sys.modules[__name__]
    fns = [(n, f) for n, f in vars(mod).items() if n.startswith("test_") and callable(f)]
    for n, f in fns:
        f()
        print(f"  ✓ {n}")
    print(f"\n{len(fns)} tests passed")
