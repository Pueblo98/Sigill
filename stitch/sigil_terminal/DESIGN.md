# Design System Strategy: Terminal Precision

## 1. Overview & Creative North Star
**Creative North Star: "The Digital Ledger"**

This design system is engineered for high-stakes prediction markets where speed of comprehension and data density are the primary currencies. Moving beyond standard "flat" dashboards, "The Digital Ledger" adopts a brutalist yet sophisticated aesthetic inspired by high-end financial terminals. 

The system rejects the "rounded and friendly" trend of modern SaaS. Instead, it embraces a **Hard-Edge Architecture**—utilizing 0px border radii and high-density spacing to signal authority and professional rigor. By utilizing intentional asymmetry and a dual-typeface system (Inter for narrative, JetBrains Mono for data), we create a "tactile digital" experience that feels like a precision instrument rather than a consumer app.

---

## 2. Colors & Surface Logic
The palette is rooted in a "Void" aesthetic, using a spectrum of near-blacks to define depth rather than structural lines.

### Surface Hierarchy & Nesting
To achieve a "Bloomberg" level of density without visual clutter, we prohibit 1px solid borders for sectioning. Boundaries are defined solely through background shifts:
- **Base Layer:** `surface_container_lowest` (#0e0e10) for the main application background.
- **Sectioning:** `surface_container_low` (#1b1b1d) for secondary sidebars or navigation rails.
- **Actionable Cards:** `surface_container` (#201f21) for the primary trading widgets.
- **Active/Hover State:** `surface_bright` (#39393b) to indicate focus.

### The "No-Line" Rule
Traditional borders are replaced by **Tonal Stepping**. When two containers meet, their difference in hex value provides the separation. This allows the user's eye to glide across data points without being snagged by unnecessary "grid-cell" outlines.

### Glass & Gradient Rule
While the system is high-density, main CTAs and "floating" execution panels should use **Glassmorphism**. Apply `primary_container` (#7c3aed) at 80% opacity with a `20px` backdrop-blur. This "Frosted Violet" effect ensures the primary brand color feels like a light source within the dark interface.

---

## 3. Typography
The system uses a strict bifurcated typographic scale to separate "UI Instruction" from "Live Data."

*   **UI Typography (Inter):** Used for labels, navigation, and descriptive text. Inter’s tall x-height ensures readability at the compact `body-sm` (0.75rem) scale required for dense layouts.
*   **Data Typography (JetBrains Mono):** Used for all prices, percentages, odds, and timestamps. Monospacing prevents "jumping" numbers during live updates and aligns perfectly in vertical columns, essential for order books and price feeds.

**Key Scales:**
- **Display-LG (3.5rem):** Reserved for market-defining outcomes.
- **Label-SM (0.6875rem):** Uppercase, letter-spaced +5% for secondary metadata.
- **Title-SM (1rem):** Bold Inter for widget headers.

---

## 4. Elevation & Depth
In a high-density environment, traditional drop shadows create "muddy" interfaces. We use **Tonal Layering** and **Ambient Glows**.

*   **The Layering Principle:** Depth is achieved by stacking. A `surface_container_highest` widget sits on a `surface_container_low` background. The "lift" is perceived through contrast, not shadow.
*   **Ambient Glows:** For "Active" trades or "Live" status, use a `primary` (#d2bbff) shadow with a 32px blur at 10% opacity. This mimics the glow of a CRT terminal phosphor.
*   **The Ghost Border:** If a visual anchor is required (e.g., a hover state on a complex chart), use the `outline_variant` (#4a4455) at **15% opacity**. Never use 100% opaque borders.

---

## 5. Components

### Execution Buttons
- **Primary:** `primary_container` (#7C3AED) background, 0px radius. Use `on_primary_container` (#ede0ff) for text.
- **Secondary/Ghost:** `surface_container_highest` with a `Ghost Border`. 
- **Interaction:** On click, use a 1px `primary` inset glow to simulate a physical terminal button being pressed.

### Data Chips
- **Selection Chips:** No background. Use a `primary` 2px bottom-bar to indicate selection.
- **Status Chips (Success/Danger):** Use `emerald-500` and `rose-500` text only, paired with a subtle 10% opacity background of the same color. 0px radius.

### Order Book & Lists
- **Rule:** Forbid divider lines.
- **Separation:** Use `0.3rem` (Spacing 2) of vertical whitespace between rows. For high-density tables, use alternating row tints: `surface_container_low` and `surface_container`.
- **Leading Elements:** Monospaced numbers (JetBrains Mono) must be right-aligned to ensure decimal points align perfectly.

### Inputs & Fields
- **Container:** `surface_container_lowest` (#0e0e10). 
- **Focus State:** No "glow." The background shifts to `surface_container_highest` and the label (Inter, `label-sm`) changes to `primary` color.

---

## 6. Do’s and Don’ts

### Do:
- **Align to the 0.15rem Grid:** Every element must snap to the spacing scale. Inconsistent 1px offsets destroy the professional "terminal" feel.
- **Use "Data-First" Hierarchy:** If a price is changing, it should be the most visually prominent element in the widget.
- **Embrace Asymmetry:** Use wide columns for charts and narrow columns for order books. Avoid 50/50 splits which feel like generic templates.

### Don’t:
- **Don't use Rounded Corners:** 0px is the law. Rounding introduces "consumer-grade" softness that undermines the platform's professional intent.
- **Don't use High-Contrast Dividers:** If the UI feels cluttered, increase whitespace (Spacing Scale 4 or 5) instead of adding a line.
- **Don't use "Pure" White:** Only use `on_surface` (#e5e1e4) for text to prevent eye strain during long-duration trading sessions.