"""Throwaway probe: do the Kalshi + Polymarket public feeds work today?

Hits each platform's REST /markets endpoint, picks a few real market IDs,
opens the WS subscription, listens ~20 seconds, and reports counts +
message shapes. Use to verify the wire format matches what
``sigil/ingestion/kalshi.py`` + ``sigil/ingestion/polymarket.py`` expect
before plumbing a bootstrap.

NOT a smoke test (no asserts). Stdout is the diagnostic.

Usage:

    .venv/Scripts/python.exe scripts/probe_feeds.py
    .venv/Scripts/python.exe scripts/probe_feeds.py --listen 30
    .venv/Scripts/python.exe scripts/probe_feeds.py --kalshi-only
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from collections import Counter
from typing import Any, Dict, List

import httpx
import websockets

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)


KALSHI_REST = "https://api.elections.kalshi.com/trade-api/v2"
KALSHI_WS = "wss://api.elections.kalshi.com/trade-api/ws/v2"
POLYMARKET_REST = "https://clob.polymarket.com"
POLYMARKET_WS = "wss://ws-subscriptions-clob.polymarket.com/ws/market"


def _hr(label: str) -> None:
    print(f"\n=== {label} ===")


def _summarize_record(d: dict, depth: int = 0, max_depth: int = 1) -> str:
    """Compact 'key: type(value)' rendering for one JSON record."""
    if depth >= max_depth:
        return type(d).__name__
    if not isinstance(d, dict):
        return type(d).__name__
    parts = []
    for k, v in d.items():
        if isinstance(v, dict):
            parts.append(f"{k}:dict({len(v)})")
        elif isinstance(v, list):
            inner = type(v[0]).__name__ if v else "?"
            parts.append(f"{k}:list[{inner}]({len(v)})")
        else:
            tval = type(v).__name__
            sval = str(v)
            if len(sval) > 30:
                sval = sval[:27] + "..."
            parts.append(f"{k}:{tval}({sval})")
    return "{ " + ", ".join(parts) + " }"


# --- Kalshi -------------------------------------------------------------- #

async def probe_kalshi(listen_seconds: int) -> None:
    _hr("Kalshi REST /markets")
    async with httpx.AsyncClient(base_url=KALSHI_REST, timeout=15.0) as client:
        try:
            r = await client.get("/markets", params={"limit": 25, "status": "open"})
        except Exception as exc:
            print(f"[REST] FAIL connect: {type(exc).__name__}: {exc}")
            return
        print(f"[REST] HTTP {r.status_code}")
        if r.status_code != 200:
            print(f"[REST] body[:300]: {r.text[:300]}")
            return
        body = r.json()
        markets = body.get("markets", [])
        print(f"[REST] markets returned: {len(markets)}")
        if not markets:
            print("[REST] no open markets returned")
            return
        # Show first record's shape so we can compare to KalshiDataSource.normalize
        print(f"[REST] first record shape: {_summarize_record(markets[0])}")
        sample_tickers = [m.get("ticker") for m in markets[:5] if m.get("ticker")]
        print(f"[REST] sample tickers: {sample_tickers}")

    if not sample_tickers:
        return

    _hr(f"Kalshi WS (listening {listen_seconds}s)")
    msg_types: Counter[str] = Counter()
    sample_msgs: List[Dict[str, Any]] = []
    received = 0
    started = time.monotonic()
    try:
        async with websockets.connect(KALSHI_WS, open_timeout=10) as ws:
            sub = {
                "id": 1,
                "cmd": "subscribe",
                "params": {
                    "channels": ["orderbook_delta"],
                    "market_tickers": sample_tickers,
                },
            }
            await ws.send(json.dumps(sub))
            print(f"[WS]   connected, sent subscribe for {len(sample_tickers)} tickers")
            try:
                while time.monotonic() - started < listen_seconds:
                    remaining = listen_seconds - (time.monotonic() - started)
                    raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
                    received += 1
                    try:
                        data = json.loads(raw)
                    except Exception:
                        msg_types["<non-json>"] += 1
                        continue
                    msg_types[data.get("type", "<no-type>")] += 1
                    if len(sample_msgs) < 3:
                        sample_msgs.append(data)
            except asyncio.TimeoutError:
                pass
    except Exception as exc:
        print(f"[WS]   FAIL: {type(exc).__name__}: {exc}")
        return

    print(f"[WS]   total messages: {received}")
    print(f"[WS]   types: {dict(msg_types)}")
    for i, m in enumerate(sample_msgs):
        print(f"[WS]   sample[{i}] shape: {_summarize_record(m)}")
        # If it has a 'msg' subkey (orderbook_delta), peek into it
        if isinstance(m.get("msg"), dict):
            print(f"[WS]   sample[{i}].msg: {_summarize_record(m['msg'])}")


# --- Polymarket ---------------------------------------------------------- #

async def probe_polymarket(listen_seconds: int) -> None:
    _hr("Polymarket REST /markets")
    async with httpx.AsyncClient(base_url=POLYMARKET_REST, timeout=15.0) as client:
        try:
            r = await client.get("/markets", params={"active": "true", "closed": "false"})
        except Exception as exc:
            print(f"[REST] FAIL connect: {type(exc).__name__}: {exc}")
            return
        print(f"[REST] HTTP {r.status_code}")
        if r.status_code != 200:
            print(f"[REST] body[:300]: {r.text[:300]}")
            return
        body = r.json()
        # Polymarket sometimes returns {"data": [...]}, sometimes a bare list.
        data = body.get("data", body) if isinstance(body, dict) else body
        if not isinstance(data, list):
            print(f"[REST] unexpected body shape: {type(body).__name__}; keys={list(body.keys())[:8]}")
            return
        print(f"[REST] markets returned: {len(data)}")
        if not data:
            return
        first = data[0]
        print(f"[REST] first record shape: {_summarize_record(first)}")
        # tokens[].token_id is what the WS subscribes to; condition_id identifies market
        # Filter: actually-trading markets only.
        live = [
            m for m in data
            if m.get("accepting_orders") and m.get("enable_order_book")
            and not m.get("closed") and not m.get("archived")
        ]
        print(f"[REST] live (accepting_orders + enable_order_book + !closed + !archived): {len(live)}")
        if live:
            print(f"[REST] live sample question: {live[0].get('question', '')[:80]}")
        sample_tokens: List[str] = []
        sample_conditions: List[str] = []
        for m in live[:8]:
            cid = m.get("condition_id")
            if cid and len(sample_conditions) < 5:
                sample_conditions.append(cid)
            tokens = m.get("tokens") or []
            for t in tokens:
                tok = t.get("token_id") if isinstance(t, dict) else None
                if tok:
                    sample_tokens.append(tok)
                if len(sample_tokens) >= 5:
                    break
            if len(sample_tokens) >= 5:
                break
        print(f"[REST] sample condition_ids: {[c[:12]+'…' for c in sample_conditions]}")
        print(f"[REST] sample token_ids: {[t[:12]+'…' for t in sample_tokens]}")

    if not sample_tokens:
        print("[WS]   skip: no token_ids extracted")
        return

    _hr(f"Polymarket WS (listening {listen_seconds}s)")
    msg_types: Counter[str] = Counter()
    sample_msgs: List[Any] = []
    received = 0
    started = time.monotonic()
    try:
        async with websockets.connect(POLYMARKET_WS, open_timeout=10) as ws:
            sub = {"assets_ids": sample_tokens, "type": "market"}
            await ws.send(json.dumps(sub))
            print(f"[WS]   connected, sent subscribe for {len(sample_tokens)} token_ids")
            try:
                while time.monotonic() - started < listen_seconds:
                    remaining = listen_seconds - (time.monotonic() - started)
                    raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
                    received += 1
                    try:
                        data = json.loads(raw)
                    except Exception:
                        msg_types["<non-json>"] += 1
                        continue
                    if isinstance(data, list):
                        msg_types[f"list[{len(data)}]"] += 1
                        if len(sample_msgs) < 3 and data:
                            sample_msgs.append(data[0])
                    elif isinstance(data, dict):
                        msg_types[data.get("event_type") or data.get("type") or "<dict>"] += 1
                        if len(sample_msgs) < 3:
                            sample_msgs.append(data)
                    else:
                        msg_types[type(data).__name__] += 1
            except asyncio.TimeoutError:
                pass
    except Exception as exc:
        print(f"[WS]   FAIL: {type(exc).__name__}: {exc}")
        return

    print(f"[WS]   total messages: {received}")
    print(f"[WS]   types: {dict(msg_types)}")
    for i, m in enumerate(sample_msgs):
        print(f"[WS]   sample[{i}] shape: {_summarize_record(m)}")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--listen", type=int, default=20)
    parser.add_argument("--kalshi-only", action="store_true")
    parser.add_argument("--poly-only", action="store_true")
    args = parser.parse_args()

    if not args.poly_only:
        await probe_kalshi(args.listen)
    if not args.kalshi_only:
        await probe_polymarket(args.listen)
    print("\n[done]")


if __name__ == "__main__":
    asyncio.run(main())
