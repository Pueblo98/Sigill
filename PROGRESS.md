# Progress Report — Sigil

### [2026-03-29] - AI Collaboration Protocol Setup - Gemini
- **Status:** Completed
- **Accomplished:**
  - Researched project context from `docs/prd.md`.
  - Created `AI.md` with comprehensive standards for code maintenance, progress reporting, commit practices, and AI-to-AI communication.
  - Tailored the protocol specifically for the Sigil architecture (modular verticals, data-first approach).
- **Current State:**
  - `AI.md` is in the root directory.
  - `PROGRESS.md` is initialized.
- **Next Steps:**
  - Future AI agents should adhere to `AI.md` when implementing the data ingestion, modeling, or execution layers of Sigil.
  - Update `PROGRESS.md` after every development session.
- **Known Issues/Debt:**
  - None at this stage.

### [2026-03-29] - Backend Infrastructure Initialization - Gemini
- **Status:** Completed
- **Accomplished:**
  - Created project directory structure (src/sigil/ingestion, features, modeling, etc.).
  - Implemented `src/sigil/config.py` for environment-level configuration.
  - Defined core protocols in `base.py` for:
    - `DataSource` (Ingestion)
    - `FeatureExtractor` (Features)
    - `Model` (Modeling)
    - `VerticalModule` (Verticals)
  - Set up Python package structure with `__init__.py` files.
- **Current State:**
  - Foundational interfaces are defined.
- **Next Steps:**
  - See below.

### [2026-03-29] - Database Models and Kalshi Integration Skeletons - Gemini
- **Status:** Completed
- **Accomplished:**
  - Implemented `src/sigil/db.py` and `src/sigil/models.py`.
  - Defined `ExchangeAdapter` and `KalshiDataSource`.
- **Current State:**
  - Persistence layer ready.
- **Next Steps:**
  - See below.

### [2026-03-29] - Core Signal & Intelligence Systems - Gemini
- **Status:** Completed
- **Accomplished:**
  - Implemented `MarketManager`, `TelegramAlerts`, and `EloRatingExtractor`.
- **Current State:**
  - Logic engine is functional.
- **Next Steps:**
  - See below.

### [2026-03-29] - Execution Security & Orchestration - Gemini
- **Status:** Completed
- **Accomplished:**
  - Implemented Kalshi v2 RSA Signing and the main Orchestrator.
- **Current State:**
  - Heartbeat active.
- **Next Steps:**
  - See below.

### [2026-03-29] - Cross-Platform Arbitrage Detection - Gemini
- **Status:** Completed
- **Accomplished:**
  - Implemented `MarketMatcher` and `ArbDetector` backend logic.
  - Implemented `PolymarketDataSource`.
- **Current State:**
  - Logic engine ready.
- **Next Steps:**
  - See below.

### [2026-03-29] - Frontend: Arbitrage Scanner & System Integration - Gemini
- **Status:** Completed
- **Accomplished:**
  - Designed `stitch/market_browser/arb_scanner.html`.
- **Current State:**
  - Static HTML versions ready.
- **Next Steps:**
  - See below.

### [2026-03-29] - Next.js Migration & Live Terminal Launch - Gemini
- **Status:** Completed
- **Accomplished:**
  - Initialized the unified React frontend in `sigil-frontend/`.
  - Migrated the main dashboard from "Stitch" to `app/page.tsx`.
  - Migrated the Arbitrage Scanner to `app/arbitrage/page.tsx`.
  - Configured global styles (`globals.css`) and layouts (`layout.tsx`) to adhere to the **Terminal Precision** design system.
  - Started the Next.js development server on port 3000.
- **Current State:**
  - Base Next.js app is live.
- **Next Steps:**
  - See below.

### [2026-03-29] - Frontend: Unified Layout & Page Fleshing - Gemini
- **Status:** Completed
- **Accomplished:**
  - Refactored the Next.js app to use a centralized, stateful `AppLayout` with a collapsible `Sidebar` and unified `TopNav`.
  - Re-styled all pages to ensure "PAPER MODE" is visually active and "LIVE MODE" is clearly disabled for the demo.
  - Migrated the remaining Stitch mockups into fully functional Next.js routes:
    - `Data Pipeline Health` -> `/data-health`
    - `Model Performance Analysis` -> `/models`
    - `Market Trade Detail` -> `/trade-detail`
- **Current State:**
  - The entire frontend from the `stitch` mocks has been successfully recreated in Next.js. The UI is consistent, collapsible, and strictly adheres to the "Terminal Precision" (0px radius, void palette, JetBrains Mono) aesthetic.
- **Next Steps:**
  - Implement dynamic data fetching from the Python FastAPI backend (which needs to be built) to replace the hardcoded mock data.
  - Connect the real `MarketManager` and `ArbDetector` outputs to the frontend tables.
- **Known Issues/Debt:**
  - The frontend currently uses hardcoded mock data for visualization. Charts are static SVG/CSS blocks that need to be replaced with dynamic `recharts` components once real data is flowing.

### [2026-05-02] - Markets / Spreads formatting parity - Claude
- **Status:** Completed
- **Accomplished:**
  - Aligned the Markets All/Archived tab and the Cross-platform spreads tab so they share the same color + link conventions row-by-row.
  - Markets table cells now match the spread widget's pattern: muted-color cells get `<td class="num-mute">`, polarity-colored values stay on `<span class="num-pos|num-neg">` inside the `<td>`. Status column is now `num-mute` (was plain). Last-price cell is now wrapped in `<a href="/market/{external_id}">` so the Last column is itself clickable, not just the title.
  - Cross-platform spreads widget (`src/sigil/dashboard/widgets/cross_platform_spreads.py`):
    - Added `kalshi_external_id` + `polymarket_external_id` (Optional[str], default None) to `SpreadRow` dataclass. Old `kalshi_url` / `polymarket_url` fields are kept on the dataclass for back-compat but no longer referenced by `render()`.
    - `fetch()` populates the new fields from `kalshi.external_id` / `poly.external_id`.
    - `render()` emits internal `<a href="/market/{external_id}">` links on the Question, Kalshi YES, and Polymarket YES cells. Falls back to plain text when an external_id is unavailable. Question column prefers Kalshi side (richer per-market data), falls back to Polymarket.
    - All `target="_blank"` and external `kalshi.com` / `polymarket.com` links removed — clicks now stay inside the dashboard.
  - Test updates in `tests/dashboard/test_cross_platform_spreads.py`:
    - Renamed `test_renders_table_with_links` → `test_renders_table_with_internal_links`. Asserts `href="/market/{ext_id}"` for both sides; asserts `kalshi.com/markets` and `target="_blank"` are NOT in output.
    - New test `test_question_falls_back_to_polymarket_id_if_no_kalshi` covers the kalshi-side-missing fallback path.
- **Current State:**
  - 184 dashboard tests pass (183 prior + 1 new test).
  - Both Markets All tab and Spreads tab render with the same `num-mute / num-pos / num-neg` convention. Click-through is consistent: every clickable element on either tab points to `/market/{external_id}` inside the dashboard. External-link leak count: 0 in either view.
- **Next Steps:**
  - Polymarket condition_id markets that haven't been ingested into our `Market` table yet will 404 when clicked from a spread row. The link still constructs cleanly; the user just sees a "Market not found" page. If this becomes a UX issue, the spread fetch could query the DB to gate the link, but that adds a lookup per row.
- **Known Issues/Debt:**
  - Some spread rows show only one platform side (e.g. Kalshi-only) — the link to the missing platform's `/market/{id}` falls back to plain text. That's consistent with how the markets table renders rows without a price (also plain text).

### [2026-05-02] - Number colors + pulse-on-change - Claude
- **Status:** Completed
- **Accomplished:**
  - Added a `num-{pos,neg,warn,mute}` token system in `dashboard.css` so numeric stats render with stable polarity colors (gain green, loss red, attention purple, neutral muted).
  - Added a `tick-pulse-up` / `tick-pulse-down` CSS keyframe pair for a 1.8s flash + color transition. Respects `prefers-reduced-motion`.
  - New `static/tick-pulse.js` (~50 LOC, dependency-free IIFE matching `relative-time.js` style). On DOMContentLoaded it walks `[data-tick-value][data-tick-key]` elements, compares each value against a `localStorage` snapshot keyed by `sigil:tick:<key>`, and applies the appropriate pulse class for 1.8s when the value changed since the previous page render. Then writes the new value back. First render = no pulse; subsequent meta-refreshes pulse anything that moved.
  - Wired tick keys + colors into:
    - `markets_list.html` — last_price (pos when ≥0.5, neg when <0.5), vol_24h (mute).
    - `models_list.html` (card grid) — Trades, Win rate (pos when ≥50%, neg when <50%), P&L (pos/neg by sign), Drawdown (neg when >0), Predictions/24h.
    - `model_detail.html` — full 8-stat performance grid.
    - `cross_platform_spreads` widget render (Python) — Kalshi YES, Polymarket YES, Yes diff (color by sign + direction arrow). Volume + score get the `num-mute` class.
  - Registered `tick-pulse.js` in `base.html` next to the existing `relative-time.js` script tag.
- **Current State:**
  - 183 dashboard tests still pass — the changes were all template/JS/CSS, no Python logic touched in widgets beyond formatting.
  - Backend restarted on `:8003`, all surfaces render the new attributes; verified with curl that markets table, spreads tab, models card grid, and model detail all emit `data-tick-key` + `num-*` class spans.
- **Next Steps:**
  - The pulse only fires when localStorage has a previous snapshot for a given key. First page load after deployment shows colors but no pulses; second refresh onward, anything that moved flashes briefly. Operators get a felt sense of liveness.
- **Known Issues/Debt:**
  - Bankroll/portfolio summary numbers in the `bankroll_summary` widget aren't yet wired to the tick-pulse system — Python widget render emits HTML directly. If the operator wants the equity / P&L on the Command Center to pulse, that widget's `render` method needs the same data-attribute injection treatment as `cross_platform_spreads` got. Not blocking; deferred.

### [2026-05-02] - Live ingestion + sparkline fix - Claude
- **Status:** Completed
- **Accomplished:**
  - Restarted `scripts/start_ingestion.py` after a ~50-min outage; OddsPipe poll cycle now firing on the 5-min tick (was rate-limited by the prior 60s burst).
  - `ODDSPIPE_POLL_SECONDS` default: 60 → 300 in `src/sigil/config.py`. Aligns with decision 4A (5-min freshness on $50/mo tier) AND the `cross_platform_spreads` widget `cache=5m` in `dashboard.yaml` — feed and refresh now land on the same beat instead of fighting each other. Operator note: dropping back to 60s burns ~60 calls/hour and tripped 429s today; 300s burns ~12/hour, cleanly under quota.
  - Fixed the market-detail sparkline graphic. Previously `views/market_detail.py` preferred `MarketPrice.last_price` over the bid/ask mid for the 7-day price series. OddsPipe REST returns `last_traded_price` that's stale-by-hours on low-volume prediction markets even when bid/ask are moving tick-to-tick — so most markets degraded into the "Price stable at X" text fallback. Switched to mid-price first, last_price as fallback. Real markets like `KXLAYOFFSYINFO-26-494000` now render an actual SVG chart instead of a flat-stable note.
  - Stale-fallback note label updated: "Price stable" → "Mid stable" so the operator knows the system already tried the more responsive metric before giving up.
- **Current State:**
  - Backend on `:8003`, ingestion process alive in the background, polling OddsPipe every 5 min. Latest verified tick batch: 189 ticks at 03:06:08, age <30s.
  - 183 dashboard tests pass after the sparkline change.
  - Tick rate observed: 189 ticks per poll cycle (one per OddsPipe-discovered market).
  - DEV-seeded markets (random walks) and active real markets show full sparkline SVGs; genuinely flat markets still show the "Mid stable" text note (correct behavior).
- **Next Steps:**
  - Operator: verify the `/markets?view=spreads` tab repopulates with fresh arb opportunities at the next 5-min tick. The widget cache TTL (5m) and the ingestion poll cadence (5m) now align — first cache miss after this point will hit fresh OddsPipe data.
  - If 429s recur, drop to 600s rather than back to 60s — the spreads widget will still feel current at 10-min resolution.
- **Known Issues/Debt:**
  - Some Polymarket condition-id markets genuinely have flat bid/ask for weeks (long-duration political/event markets with stable consensus) — those still render the "Mid stable" note. Not a bug, just a feed reality.
  - `_preflight()` in `start_ingestion.py` still warns about Kalshi RSA-PSS creds when `DIRECT_EXCHANGE_WS_ENABLED=false`; harmless but noisy.

### [2026-05-02] - Markets Sub-Tabs (vertical IA) - Claude
- **Status:** Completed
- **Accomplished:**
  - Applied the `sigil-frontend/DESIGN.md` "vertical IA" rule to the backend dashboard: collapsed Cross-platform spreads + Archived from top-level surfaces into in-page tabs on the Markets section.
  - Added `?view=` query param to `/markets` (`all` default, `spreads`, `archived`). Legacy `?archived=1` translates to `?view=archived`.
  - `view=spreads` reuses the existing `cross_platform_spreads` widget by looking it up in `state.widgets` and rendering its cached HTML inline — no double-fetching of OddsPipe. Widget keeps refreshing via the YAML `spreads` page (kept in `dashboard.yaml`, dropped from `_nav_pages`).
  - `view=archived` replaces the old archived-checkbox semantics with a clean "non-running markets" tab (status≠open OR archived=True).
  - Refactored `views/markets_list.py::build_context` signature: `archived: Optional[str]` → `view: Optional[str]`. `MarketsListContext.archived: bool` → `MarketsListContext.view: str`.
  - New CSS namespace `.markets-list__tabs` / `.markets-list__tab{,--active}` / `.markets-list__embedded-widget` — minimal additions, no existing rules touched.
  - Topbar entry "Cross-platform spreads" removed. New order: Command Center · Markets · Execution · Models · Data Health.
- **Current State:**
  - 183 dashboard tests pass (181 prior + 2 new view-related cases on `test_markets_list_route.py`; 2 obsolete archived-checkbox tests refactored in place).
  - `/page/spreads` still 200 for old bookmarks.
  - Backend on port 8003.
- **Next Steps:**
  - TODO-11 (operator-gated frontend deletion) is the remaining blocker for `sigil-frontend/` going away.
- **Known Issues/Debt:**
  - None new.

### [2026-05-02] - Backend Dashboard Feature Parity - Claude
- **Status:** Completed
- **Accomplished:**
  - Operator preferred the Python dashboard's dark/monospace aesthetic over the Next.js frontend, so all backend-data pages migrated to the server-rendered surface.
  - Wired existing F2 widgets into `dashboard.yaml`: `source_health_table` and `error_log` joined the Health page (Models F2 widgets stay registered, see TODO-12).
  - Built `/execution` standalone route — filterable + paginated orders feed (`views/execution_log.py`, `templates/execution_log.html`). Filters: platform, mode (paper/live), status. Mode chip styled via new `.markets-list__mode-chip{,--live,--paper}` rules.
  - Built `/models/{model_id}` per-model detail page (`views/model_detail.py`, `templates/model_detail.html`). Reuses `sigil.api.model_performance.model_detail` + `render_roi_curve_svg`. Sections: header, 8-stat performance grid, equity curve, recent trades, recent predictions.
  - Built `/models` standalone card grid (`views/models_list.py`, `templates/models_list.html`) mirroring the frontend Next.js Models mechanic. One card per `ModelDef`: display name, version, status dot (live/idle/disabled), description, tags, 4-stat grid, last trade, 24h prediction count. Click-through to `/models/{id}`.
  - Removed the YAML `models` page; `_nav_pages` in `mount.py` learned to drop both `markets` and `models` YAML pages and insert standalone links at fixed topbar positions.
  - Topbar order: Command Center · Markets · Execution · Cross-platform spreads · Models · Data Health.
- **Current State:**
  - 181 dashboard tests pass; 381 across the broader suite (excluding `tests/decision/` + `tests/ingestion/` integration suites).
  - Backend Python dashboard at port 8003 has feature parity with (or beyond) the Next.js frontend at port 3000 for every backend-data page.
  - `dashboard.css` gained two scoped additions (mode chip, models card grid) — no existing rules touched.
  - Plan file: `C:\Users\simon\.claude\plans\ok-so-weve-been-bright-forest.md`.
- **Next Steps:**
  - Operator sign-off on parity, then TODO-11 deletes `sigil-frontend/`.
  - TODO-12 re-wires the analytical model widgets if/when a comparative-analytics page is felt-needed.
- **Known Issues/Debt:**
  - `tests/dashboard/test_render.py::test_old_models_yaml_page_is_404` and `test_nav_lists_all_pages` were updated to reflect the new route structure — flag for any future agent who tries to add a new YAML page named `markets` or `models` (mount.py drops them silently).
  - The pre-existing zombie-LISTEN state on Windows ports 8001/8002 persists; backend stays on 8003 until reboot (per `secrets.local.yaml` operator note).

