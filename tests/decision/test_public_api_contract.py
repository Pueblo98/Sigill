"""W2.2(e) — public-API contract for the decision module.

`/api/arbitrage` imports `StatArbScanner` from `sigil.decision.stat_arb`. The
endpoint test in `tests/api/test_routes.py` patches that exact path. If
`stat_arb.py` is ever renamed or `StatArbScanner` is moved, both the runtime
endpoint and the patch would silently break together.

This test asserts the public surface stays callable from BOTH the canonical
package import (`sigil.decision`) and the submodule path (`sigil.decision.stat_arb`).
A failure here means: update the lazy import in `api/routes.py` and the route's
patch path before merging.
"""
from __future__ import annotations

import inspect


def test_stat_arb_scanner_exposed_from_decision_package():
    import sigil.decision as decision_pkg

    assert hasattr(decision_pkg, "StatArbScanner"), (
        "sigil.decision must re-export StatArbScanner; /api/arbitrage relies on it."
    )
    assert hasattr(decision_pkg, "ArbOpportunity")


def test_stat_arb_scanner_importable_from_submodule_path():
    """The lazy import in routes.py uses `sigil.decision.stat_arb.StatArbScanner`."""
    from sigil.decision.stat_arb import StatArbScanner  # noqa: F401


def test_stat_arb_scanner_has_async_scan():
    from sigil.decision.stat_arb import StatArbScanner

    scanner = StatArbScanner()
    assert hasattr(scanner, "scan")
    assert inspect.iscoroutinefunction(scanner.scan), (
        "StatArbScanner.scan must remain async — `/api/arbitrage` awaits it."
    )


def test_decision_package_and_submodule_are_same_class():
    """If someone defines a second class with the same name, the patch in
    `tests/api/test_routes.py` would target one and the endpoint would see
    the other. Identity check guards against that."""
    import sigil.decision as decision_pkg
    from sigil.decision.stat_arb import StatArbScanner

    assert decision_pkg.StatArbScanner is StatArbScanner
