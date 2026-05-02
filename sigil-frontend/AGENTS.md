# DEPRECATION NOTICE (2026-05-02)

This Next.js frontend is **slated for deletion** under TODO-11
(see repo-root `TODOS.md`). The operator now uses the server-rendered
Python dashboard at `:8003/` (dark/monospace aesthetic preferred over
this UI). Backend dashboard feature parity landed 2026-05-02 morning;
later that day the backend also adopted this directory's
`DESIGN.md` "vertical IA" rule — Cross-platform spreads + Archived
moved into the Markets section as in-page tabs:

| This frontend page | Backend equivalent |
|---|---|
| `/` (portfolio) | `:8003/page/command-center` |
| `/markets` | `:8003/markets` (richer — server-side filter + paginate) |
| `/trade-detail/[id]` | `:8003/market/{external_id}` |
| `/arbitrage` | `:8003/markets?view=spreads` (sub-tab; `/page/spreads` still works) |
| `/data-health` | `:8003/page/health` |
| `/models` | `:8003/models` (card grid mirroring this mechanic) |
| `/models/[id]` | `:8003/models/{model_id}` |
| `/execution` | `:8003/execution` |

**Do not add new features here.** Land them in
`src/sigil/dashboard/` (server-rendered). If you must edit this dir
(e.g. emergency bugfix), keep changes minimal — this code is going
away once the operator signs off on parity.

<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

# Design rules

Read `DESIGN.md` before adding any new page, route, or top-level nav item.
Short version: navigation is **vertical**. The sidebar stays lean (a few
top-level sections); features land as sub-routes (`/section/[id]`) or stacked
sections inside an existing page, not as new sidebar tabs.

# API

Frontend talks to FastAPI at `http://localhost:8001` by default. Override via
`NEXT_PUBLIC_API_URL`.
