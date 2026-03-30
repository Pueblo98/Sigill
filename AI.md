# AI Collaboration & Maintenance Protocol — Sigil

This document defines the mandatory standards for AI agents (Claude, Gemini, etc.) working on the Sigil codebase. Its purpose is to ensure continuity, structural integrity, and clear state-sharing during multi-agent or multi-session development.

---

## 1. Core Directives

- **Context First:** Always read `docs/prd.md` and this file before initiating any structural changes.
- **Modular Integrity:** Sigil is "Modular by Default." Never introduce cross-dependencies between verticals (e.g., `sports` should never import from `politics`).
- **Surgical Execution:** Prefer precise, targeted updates over broad refactors. If a refactor is necessary, it must be performed in a dedicated, isolated session.
- **State Preservation:** You are responsible for leaving the workspace in a state that the next AI can immediately understand.

---

## 2. Progress Reporting (The "Handover" Rule)

At the end of every significant task or session, you MUST update or create a `PROGRESS.md` file in the root directory (or append to the `Decision Logs` in `docs/prd.md` if it's an architectural shift).

### Progress Report Template:
```markdown
### [YYYY-MM-DD] - Task Name - Agent Name (e.g., Gemini)
- **Status:** [In Progress | Completed | Blocked]
- **Accomplished:**
  - Brief bullet points of what was actually changed.
- **Current State:**
  - Where the logic stands. Mention specific files that are partially edited.
- **Next Steps:**
  - Explicit instructions for the next agent.
- **Known Issues/Debt:**
  - Any "TODOs" or temporary hacks introduced.
```

---

## 3. Commit Standards

When asked to commit, follow these rules to ensure the Git history remains a legible audit trail for other AIs:

- **Atomic Commits:** One feature/fix per commit.
- **Prefixes:** Use conventional prefixes:
  - `feat(vertical/module):` for new features.
  - `fix(vertical/module):` for bug fixes.
  - `refactor(module):` for code cleanup.
  - `docs:` for documentation updates.
- **Body:** Briefly explain the "Why" and "How" if the change is complex. Mention any side effects on the data pipeline or model inference.

---

## 4. Code Maintenance & Quality

### 4.1 Type Safety & Documentation
- **Type Hints:** All new Python code must use strict type hinting (`mypy` compatible).
- **Docstrings:** Use Google-style docstrings for all public classes and methods.
- **Logic Explanations:** For complex math (Kelly sizing, Elo updates), include comments explaining the formula and units.

### 4.2 Error Handling
- Never use "silent" try-except blocks.
- All exchange adapter failures must be logged with the original traceback and the raw API response (if available).

### 4.3 Validation Lifecycle
1. **Research:** Identify all affected files.
2. **Implementation:** Apply changes.
3. **Lint/Format:** Run `black` or `ruff` if available in the environment.
4. **Test:** Run existing tests. **Create a new test case for every bug fix or feature.**
5. **Verify:** Confirm the end-to-end data flow (e.g., if you change a feature extractor, verify the model still receives valid inputs).

---

## 5. Directory & Module Conventions

- **Adapters:** Exchange-specific logic stays in `src/sigil/execution/{exchange}.py`.
- **Features:** Logic for computing signals stays in `src/sigil/features/`.
- **Verticals:** New betting categories must follow the template in `src/sigil/verticals/base.py`.
- **Tests:** Mirror the `src` structure in the `tests/` directory.

---

## 6. AI-to-AI Communication

If you discover a bug or optimization opportunity *outside* your current scope:
1. **Do not fix it immediately** unless it blocks your current task.
2. **Log it** in the `Known Issues/Debt` section of your Progress Report.
3. **Notify the user** at the end of your turn.

---

## 7. Knowledge Preservation

If you make a decision that deviates from the `PRD.md`, you MUST:
1. Update the `Decision Logs` in `docs/prd.md` (§13).
2. Explain the rationale (e.g., "Switched from X to Y because the API rate limits were more restrictive than documented").

---

*“The signal is the spell. Keep the spell clean.”*
