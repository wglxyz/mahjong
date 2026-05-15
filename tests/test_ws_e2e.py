"""End-to-end: start server in-process, connect a Python client, auto-decide,
verify the full game flows over the wire."""
from __future__ import annotations
import asyncio
import json
import sys

import websockets

from server.server import App


async def _client(port: int, max_decisions: int = 5000) -> dict:
    """Connect, auto-pick the first legal action each turn, until match_ended fires."""
    uri = f"ws://127.0.0.1:{port}"
    async with websockets.connect(uri) as ws:
        decisions = 0
        result: dict = {
            "events": 0, "snapshots": 0, "decisions": 0,
            "hand_ended_count": 0, "last_hand_ended": None,
            "match_ended": None,
        }
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
                actions = msg.get("actions", [])
                if not actions:
                    break
                await ws.send(json.dumps({"type": "decide", "action_id": actions[0]["id"]}))
            elif t == "hand_ended":
                result["hand_ended_count"] += 1
                result["last_hand_ended"] = msg
            elif t == "match_ended":
                result["match_ended"] = msg
                break
            elif t == "error":
                result["error"] = msg.get("error")
                break
        return result


async def _run(ruleset: str, seed: int, port: int) -> dict:
    app = App(ruleset_name=ruleset, seed=seed)
    server = await websockets.serve(app.handle, "127.0.0.1", port)
    try:
        res = await asyncio.wait_for(_client(port), timeout=300)
    finally:
        server.close()
        await server.wait_closed()
    return res


def test_simple_ruleset_runs_to_match_end() -> None:
    res = asyncio.run(_run("simple", seed=42, port=8801))
    assert res["match_ended"] is not None, f"no match_ended: {res}"
    assert res["hand_ended_count"] >= 4, "expected at least one round (4 hands)"
    assert res["snapshots"] > 0
    assert res["events"] > 0


def test_riichi_ruleset_runs_to_match_end() -> None:
    res = asyncio.run(_run("riichi", seed=1, port=8802))
    assert res["match_ended"] is not None, f"no match_ended: {res}"
    assert res["hand_ended_count"] >= 8, "half-east default = 2 rounds × 4 hands"
    # final_points sum should equal 100000 ± stick pool drift
    final = {int(k): v for k, v in res["match_ended"]["final_points"].items()}
    total = sum(final.values())
    assert 90000 <= total <= 100000, f"final points total out of range: {total}"


def test_hand_ended_carries_winners_list() -> None:
    """Every hand_ended message must include a winners[] field (≥1 for win, [] for drawn)."""
    res = asyncio.run(_run("riichi", seed=2, port=8803))
    last = res["last_hand_ended"]
    assert last is not None
    assert "winners" in last, f"hand_ended missing winners[]: {last}"
    if last["result"] == "win":
        assert len(last["winners"]) >= 1
    else:
        assert last["winners"] == []


if __name__ == "__main__":
    import sys
    mod = sys.modules[__name__]
    fns = [(n, f) for n, f in vars(mod).items() if n.startswith("test_") and callable(f)]
    for n, f in fns:
        f()
        print(f"  ✓ {n}")
    print(f"\n{len(fns)} tests passed")
