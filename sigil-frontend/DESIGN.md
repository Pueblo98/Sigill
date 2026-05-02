# Sigil Frontend — Design Spec

This file is loaded by `AGENTS.md`. Read before adding any new page, route, or
top-level navigation entry.

## Information architecture: vertical, not horizontal

The sidebar (`components/Sidebar.tsx`) is the **only** top-level navigation
surface. It must stay short — pick a few important top-level destinations and
keep them stable. **New features land as sub-navigation inside an existing
section, not as a new top-level sidebar entry.**

Why this rule: the dashboard is a working surface, not a marketing site. A
trader scanning the sidebar should be able to commit the layout to muscle
memory in a session and never relearn it. Every time a new top-level entry
appears, the muscle memory resets and the existing entries get demoted.

### Approved top-level sections (`/components/Sidebar.tsx`)

These are deliberately broad. Resist subdividing them at the top level — go
deeper instead.

- **Dashboard** — the home overview.
- **Markets** — every market we ingest (Kalshi + Polymarket). Detail at
  `/trade-detail/[id]`.
- **Arb Scanner** — display-only cross-platform spreads.
- **Models** — every registered model. Detail at `/models/[modelId]`.
- **Trade Detail** — single-market deep dive (linked from Markets and Models).
- **Execution Log** — orders + fills feed.
- **Data Health** — ingestion + source status.

If a new feature genuinely doesn't fit any of these, the conversation is
"should we collapse two existing entries before adding a new one?" — not
"let's add an eighth tab."

### Sub-navigation (the vertical pattern)

Within a section, use one of these patterns — pick the lightest that works:

1. **Detail route** (`/section/[id]`) for "one of many" — like `/markets/[id]`,
   `/models/[modelId]`. The section page is a list/grid; the detail page is
   per-item. **No tabs.**
2. **In-page tab strip** (vertical panel switching, single route) for two or
   three sibling views of the *same* entity. Render as a slim bar of
   underlined-on-active labels at the top of the content column. Don't bother
   with a router segment unless deep-linking matters.
3. **Stacked sections** (no tabs) when the content is short enough to scroll.
   This is the default — try it first. Most "tabs" are just sections that
   wanted to be one scroll.

If you find yourself reaching for a fourth pattern, ask. Don't invent a new
one because a single page felt cramped — denser layout is almost always the
right answer over more navigation.

## Layout: stack vertically, not horizontally

Pages should read top-to-bottom in a single primary column. Side-by-side
layouts are reserved for genuinely paired data (e.g. Markets sidebar filters
+ grid). Default to:

- Header (route name, one-line subtitle, optional right-aligned meta count).
- Stat strip / KPI row.
- Primary visualization (chart, big card, etc.).
- Tables / detail rows below.

The model detail page (`app/models/[modelId]/page.tsx`) is the reference
implementation: header → 6-stat strip → equity curve → trades table →
predictions table. Every section is full-width within `max-w-6xl` and stacks.

## Visual tokens (already in use — do not invent new ones)

Background: `#0e0e10` · surface: `#201f21` / `#1b1b1d` · border: `#1b1b1d` /
`#39393b` · text: `#e5e1e4` (primary), `#958da1` (muted) · accent: `#7C3AED`
(purple), `#d2bbff` (light purple) · win: `emerald-400` · loss: `rose-400`.

Typography: Inter for prose, JetBrains Mono for any number, ID, ticker, or
status pill. Stat values are mono. Page headlines are `font-black tracking-tight`.

## API connection

Frontend talks to FastAPI on **`http://localhost:8003`** (the default in
`lib/api/client.ts`; bumped from 8000→8001→8002→8003 as Windows zombie
LISTEN sockets accumulated on this dev box). Override via
`NEXT_PUBLIC_API_URL` for non-default deployments. SWR polls every 5s
(`DEFAULT_REFRESH_INTERVAL_MS`).

## Adding a feature: checklist

Before adding a new page / route / nav item, verify:

- [ ] Does this belong inside an existing top-level section? (Default: yes.)
- [ ] Can it be a detail route (`/section/[id]`) instead of a tab?
- [ ] Can it be a stacked section on an existing page instead of a new route?
- [ ] If it really must be a new top-level nav item — what existing item are
      you proposing we merge or remove first?
