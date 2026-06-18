# Research Report Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a mandatory research-language conversion boundary, improve board/fund-flow routing, and produce session-aware report artifacts that overwrite within the same trading session.

**Architecture:** Internal evidence remains diagnostic and machine-readable. A new `research_style` module creates a separate research-only view for the LLM and validates the returned Markdown before persistence. A focused market routing module shares board and fund-flow acquisition between evidence generation and `young a`; report artifacts use a date/session/topic identity.

**Tech Stack:** Python 3.9+, requests, Click, Rich, pytest, optional Camofox/Playwright.

---

### Task 1: Mandatory research-language conversion

**Files:**
- Create: `src/young_stock/research_style.py`
- Modify: `src/young_stock/reports.py`
- Test: `tests/test_research_style.py`
- Test: `tests/test_llm_reports.py`

- [ ] Write failing tests for Markdown-wrapped internal fields, forbidden terms, paths, extensions, missing-data wording, and input immutability.
- [ ] Run the focused tests and verify the current implementation fails.
- [ ] Implement `to_research_evidence(evidence)` with explicit module/field mappings and no mutation.
- [ ] Implement `review_research_report(markdown, evidence)` with sentence-level rejection and research-language replacement.
- [ ] Make `generate_llm_daily_report()` use only the converted evidence and reject output that still fails the final scan.
- [ ] Run focused tests and commit.

### Task 2: Unified board and fund-flow routing

**Files:**
- Create: `src/young_stock/market_routes.py`
- Modify: `src/young_stock/_core.py`
- Modify: `src/young_stock/evidence.py`
- Test: `tests/test_market_routes.py`
- Test: `tests/test_core.py`
- Test: `tests/test_evidence.py`

- [ ] Write failing tests for route ordering, no-proxy Eastmoney access, structured browser rows, historical-date discipline, and final browser attempt.
- [ ] Run the focused tests and verify failures.
- [ ] Implement the shared board route without changing stable quote/index functions.
- [ ] Implement the shared fund-flow route while preserving source semantics.
- [ ] Route `young a` and Evidence construction through the shared functions.
- [ ] Run focused tests and commit.

### Task 3: Session-aware artifact identity

**Files:**
- Modify: `src/young_stock/artifacts.py`
- Modify: `src/young_stock/cli.py`
- Modify: `src/young_stock/pdf.py`
- Modify: `src/young_stock/channels/__init__.py`
- Test: `tests/test_artifacts.py`
- Test: `tests/test_pdf.py`
- Test: `tests/test_cli.py`

- [ ] Write failing tests for early, intraday, midday, after-close names; topic slugs; same-session overwrite; and cross-session retention.
- [ ] Run focused tests and verify failures.
- [ ] Add a `ReportIdentity` value object with date, session, topic, and stable prefix.
- [ ] Write Markdown, Evidence, metadata, HTML, and PDF using the same prefix.
- [ ] Update latest-report lookup to prefer current session identities and ignore legacy generic files when a new identity exists.
- [ ] Run focused tests and commit.

### Task 4: Documentation, migration, and verification

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `pyproject.toml`
- Modify: `src/young_stock/__init__.py`
- Test: `tests/test_packaging_docs.py`

- [ ] Document research-language guarantees, data route behavior, report names, and overwrite semantics.
- [ ] Bump the patch version.
- [ ] Run full pytest.
- [ ] Run ruff and `git diff --check`.
- [ ] Build wheel and source archive.
- [ ] Install the wheel in the Python 3.9 smoke environment and verify CLI help/version.
- [ ] Commit, push `main`, tag, publish, and verify GitHub/PyPI.
