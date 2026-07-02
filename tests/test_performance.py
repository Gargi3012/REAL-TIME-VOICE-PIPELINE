"""
Performance benchmarks and memory-leak detection for the session layer.

Run with: pytest tests/test_performance.py -v -s
"""

from __future__ import annotations

import gc
import sys
import time
import tracemalloc

import pytest

from app.session import SessionManager, SessionState


# ──────────────────────────────────────────────────────────────
# Benchmarks
# ──────────────────────────────────────────────────────────────

class TestCreationPerformance:
    """Session creation throughput at various scales."""

    @pytest.mark.parametrize("count", [100, 1_000, 10_000])
    def test_create_sessions(self, count: int) -> None:
        mgr = SessionManager()
        start = time.perf_counter()
        for _ in range(count):
            mgr.create_session()
        elapsed = time.perf_counter() - start
        assert mgr.total_sessions() == count
        per_op = (elapsed / count) * 1_000_000  # microseconds
        print(f"\n  create_session × {count:>6,}: {elapsed:.4f}s ({per_op:.1f} µs/op)")


class TestLookupPerformance:
    """get_session lookup at scale."""

    @pytest.mark.parametrize("count", [100, 1_000, 10_000])
    def test_lookup(self, count: int) -> None:
        mgr = SessionManager()
        ids = [mgr.create_session().session_id for _ in range(count)]

        start = time.perf_counter()
        for sid in ids:
            mgr.get_session(sid)
        elapsed = time.perf_counter() - start
        per_op = (elapsed / count) * 1_000_000
        print(f"\n  get_session × {count:>6,}: {elapsed:.4f}s ({per_op:.1f} µs/op)")


class TestMessagePerformance:
    """Message insertion and history retrieval throughput."""

    def test_insert_1000_messages(self) -> None:
        mgr = SessionManager()
        s = mgr.create_session()
        start = time.perf_counter()
        for i in range(1_000):
            mgr.add_message(s.session_id, "user", f"message-{i}")
        elapsed = time.perf_counter() - start
        per_op = (elapsed / 1_000) * 1_000_000
        print(f"\n  add_message × 1,000: {elapsed:.4f}s ({per_op:.1f} µs/op)")

    def test_retrieve_1000_history(self) -> None:
        mgr = SessionManager()
        s = mgr.create_session()
        for i in range(1_000):
            mgr.add_message(s.session_id, "user", f"message-{i}")

        start = time.perf_counter()
        for _ in range(100):
            mgr.get_history(s.session_id)
        elapsed = time.perf_counter() - start
        per_op = (elapsed / 100) * 1_000
        print(f"\n  get_history (1000 msgs) × 100: {elapsed:.4f}s ({per_op:.1f} ms/op)")


# ──────────────────────────────────────────────────────────────
# Memory leak detection
# ──────────────────────────────────────────────────────────────

class TestMemoryLeak:
    """Create-delete cycles must not leak memory."""

    def test_create_delete_cycle(self) -> None:
        mgr = SessionManager()
        gc.collect()
        tracemalloc.start()

        # Warm-up
        for _ in range(100):
            s = mgr.create_session()
            mgr.add_message(s.session_id, "user", "warmup")
            mgr.delete_session(s.session_id)

        snapshot1 = tracemalloc.take_snapshot()

        # Stress cycle
        for _ in range(5_000):
            s = mgr.create_session()
            mgr.add_message(s.session_id, "user", "test message content")
            mgr.delete_session(s.session_id)

        gc.collect()
        snapshot2 = tracemalloc.take_snapshot()

        assert mgr.total_sessions() == 0

        stats = snapshot2.compare_to(snapshot1, "lineno")
        total_leaked_kb = sum(s.size_diff for s in stats) / 1024
        print(f"\n  Memory delta after 5k create-delete cycles: {total_leaked_kb:.1f} KB")

        # Allow reasonable overhead but catch real leaks (>5 MB)
        assert total_leaked_kb < 5_000, f"Possible memory leak: {total_leaked_kb:.1f} KB"

        tracemalloc.stop()
