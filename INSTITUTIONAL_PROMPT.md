# BioTerminal Pro — Institutional & Lifecycle Build Prompt

## Mission

Evolve BioTerminal Pro from a public-equity biotech terminal into a **single research
workbench that follows a company across its whole life — private → pre-IPO → public** —
usable by a small fund, a sophisticated individual, or a VC/PE diligence team, at a rigor a
Bloomberg user would respect and a price they would not.

Two users share one product:

- **The public-market analyst** — pipeline-first, catalyst-driven, rNPV-literate. Researches
  HK + US (+ China/NMPA cross-border) biotechs. Wants trial-level depth, institutional flow,
  competitive landscape, and defensible valuation.
- **The private-market diligence user (VC/PE, operator, advisor)** — evaluates private /
  pre-IPO biotechs that have no ticker, no price, no yfinance. Values them by pipeline rNPV,
  funding-round comps, and licensing-deal comps, and attaches their own data-room material.

The bridge between them is a **compliance wall** (see §0). It is the most important part of
this build. Read it first; it is a hard constraint on everything else.

## The measuring stick

> Would a professional biotech investor open this every morning and trust what it shows —
> and would it keep them on the right side of securities law by construction, not by luck?

Award criteria may be noted as context but never drive a design decision. Trust and legality
drive every decision.

---

## §0 — The compliance wall (HARD CONSTRAINT — build this first, or don't build the private layer at all)

The product lets users capture **proprietary / private information** (notes from management
meetings, investor dinners, founder conversations, data rooms). This capability is legitimate
and valuable **only** if it is walled off from public-security signals by construction. Built
without the wall, it is an insider-trading assistance tool. It must not be.

**The line (state it in the UI and in `AI_GOVERNANCE.md`):** Material non-public information
(MNPI) about a **public** company — or a public peer/supplier/customer of a private one
(*shadow trading*, per *SEC v. Panuwat*, 2021) — may **not** be used to trade or to generate a
trade-oriented signal. Trading on MNPI is insider trading.

**Required architecture:**

1. **Provenance-first capture.** Every private note is stored as a first-class object with:
   `source` (person/role/context), `date`, `subject_entity`, `free_text`, and a required
   user classification: *is the subject (or a tradable peer) publicly listed?* and *is this
   information material and non-public?*
2. **Automatic MNPI triage.** On save, if `subject_entity` (or a linked peer) resolves to a
   public ticker AND the user flags it material+non-public, the system:
   - Adds that ticker to the user's **personal restricted list**.
   - **Suppresses** all trade-oriented outputs for that ticker (confidence signal, screener
     inclusion, backtest, DCF "upside", scenarios) and replaces them with a
     "Restricted — you hold potential MNPI on this name" banner.
   - Writes an immutable, timestamped audit-log entry (who/when/why restricted).
   - **Never** feeds the note text into any computed public signal, ever.
3. **Private notes stay private and local.** Never sent to any external service — including the
   LLM — unless the note's subject is a **private** company (no tradable security) and the user
   opts in. Public-name notes are display-only, visible to their author, and computationally
   inert with respect to any signal.
4. **Private companies are exempt.** For a private entity with no public security, user-supplied
   data legitimately feeds that entity's own valuation/diligence — there is nothing to abuse.
5. **Reframe the feature as compliance, not exploitation.** The pitch is: *BioTerminal is the
   tool that helps you stay compliant* — a personal information barrier and restricted-list
   manager — not one that helps you exploit secrets. This is also what an institutional buyer's
   compliance team would require before adoption.

**Acceptance test for §0:** Log a note "CFO told me at dinner Phase 3 will miss" against a
public ticker, flagged material+non-public. Assert: ticker is restricted, confidence/screener/
backtest for it are suppressed with the banner, an audit entry exists, and the note text appears
in **no** API response that computes a signal. This test must exist and pass before any private
capture UI ships.

---

## §1 — The Private Company entity model (private → IPO → public lifecycle)

A private biotech has no ticker, no price, no OHLCV, no yfinance, no DCF, no backtest. Do not
fake any of these. Introduce a distinct entity type.

- **Entity resolution.** Let a user create/lookup a company by name (not ticker). Persist a
  lightweight company record with a stable internal id and a `listing_status`
  (`private | pre_ipo | public`) that can transition over time. When a private company IPOs,
  the record links to its new ticker — its history (notes, prior rNPV, funding rounds) carries
  forward. This continuity is the "lifecycle" differentiator.
- **Credible public data for private companies** (all free, all citable — enforce §5 provenance):
  - **ClinicalTrials.gov** by `LeadSponsorName` — reuse the existing lead-sponsor-filtered
    fetch (`data_fetcher`, already dedupes by phase/indication). This is the pipeline.
  - **NIH RePORTER** (api.reporter.nih.gov) — federal grant funding as an R&D-depth signal.
  - **USPTO / patent** search by assignee — exclusivity runway proxy.
  - **SEC EDGAR** full-text — catch S-1 / 424B / D filings for pre-IPO names.
  - **Press releases / news** — funding rounds, readouts.
- **Valuation for private entities = rNPV only**, driven by the company's *actual*
  ClinicalTrials.gov pipeline (the existing `rnpv_calculator.py`, which already filters lead
  sponsor and shows assumptions). Add **comps**: (a) **funding-round comps** (last round
  post-money vs pipeline stage) and (b) **licensing-deal comps** using the industry heuristic
  that a licensor typically captures **25–35% of the licensee's rNPV** as total deal value.
  Label every comp with its source and vintage.
- **Data-room attachment.** Let the user attach their own documents/notes to a private entity
  (this is the legitimate home for proprietary information under §0). These feed the private
  entity's diligence view and, with opt-in, its LLM summarization — because there is no public
  security to abuse.
- **Backend:** model this as a new adapter/entity path, not a bolt-on to the ticker routes.
  Suggested: `entities/` module or a `PrivateCompanyAdapter`, plus routes
  `GET /api/company/{id}` and `POST /api/company` that return the private-entity shape. Keep all
  existing ticker routes untouched (additive-only rule).
- **Frontend:** a new entity-picker mode (name search → private record) and a private-company
  panel set that renders **only** the meaningful tabs (Pipeline, rNPV, Filings, Notes/Data-room,
  Comps) and hides price/DCF/backtest/scenarios. Reuse existing tab components where the shape
  matches.

**Acceptance:** Create a private entity (e.g. a named pre-IPO biotech), pull its real
ClinicalTrials.gov pipeline, compute an rNPV from that actual pipeline with visible assumptions,
show funding/deal comps with sources, attach a note — with no price/DCF/backtest anywhere in the
view.

---

## §2 — Institutional depth on the public side (close the diligence gaps)

The buy-side loop is: **catalyst → probability of approval → institutional/insider flow →
diligence checklist → read the clinical data → size the position.** Catalysts, runway, and
honest rNPV already exist. Close the rest. Each item: real data + provenance + honest empty
state; no placeholder numbers.

1. **Trial-level depth** (extend `pipeline_analyzer.py` / Pipeline tab). Surface per active
   trial: primary/secondary **endpoints**, **comparator/control arm**, **enrollment actual vs
   planned**, primary completion date. All available from the ClinicalTrials.gov v2 API fields
   already being fetched. This is the "reads protocols for fun" depth.
2. **Institutional & insider flow** (close the P1-4 / P2-5 stubs). US: **13F** institutional
   ownership, **insider transactions** (Form 4), **short interest**. Wire into the existing
   Ownership tab / `GET /api/ownership`. HK: the CCASS flow already exists — keep it.
3. **Competitive landscape per indication.** For a lead asset's indication, list other
   sponsors/trials in the same indication+phase (ClinicalTrials.gov query by condition+phase).
   Answers "who else is in this race" — a core diligence question Bloomberg answers poorly for
   small caps. New tab or an extension of Peers.
4. **Deal comps.** A biotech-native comps view: recent licensing/M&A deals in the asset's
   modality/indication, and the 25–35%-of-rNPV licensing heuristic applied to the subject.
5. **Catalyst calendar hardening.** Ensure PDUFA/AdComm/readout dates carry a probability-of-
   success and link back to the specific trial. (Catalysts tab already exists — deepen it.)

**Acceptance:** For `MRNA` and `6160.HK`, Pipeline shows endpoints + enrollment-vs-plan for lead
programs; Ownership shows real 13F/insider/short (US) and CCASS (HK); a competitive-landscape
view lists same-indication rivals; every field cites its source via `/api/sources`.

---

## §3 — China / NMPA + cross-border GBA depth (the moat, not a checkbox)

HK + US are done. Add **Mainland China / NMPA** as the next region, framed around the GBA
cross-border story that a HK-based product uniquely owns — and that Bloomberg covers thinly for
small/mid-caps.

- **New `ChinaExchangeAdapter`** (`exchanges/cn.py`, registered in `exchanges/__init__.py`),
  following the existing adapter ABC. Handle A-share / STAR Market tickers.
- **NMPA drug-approval signal** — surface NMPA approval/registration status for a pipeline asset
  where obtainable from a credible, citable source; otherwise show an honest "not available"
  state (never fabricate).
- **Cross-border / dual-listing depth.** Extend the existing `dual_listing.py` beyond price
  premium/discount: same asset's regulatory status across FDA / NMPA / (later) EMA, and
  A/H/US share-class mapping. This is the "one asset, three regulators" view no consumer tool
  offers.
- **Do not spread further geographically yet.** EMA/PMDA are explicitly out of scope for this
  phase — depth over breadth.

**Acceptance:** A GBA biotech (e.g. BeiGene 6160.HK / its A-share / US line) shows a unified
cross-border view: HK + US price, and the same lead asset's status across FDA and NMPA, each
citation-backed.

---

## §4 — Data credibility & provenance (the trust substrate for all of the above)

Institutional trust dies on one fabricated or stale number. Make provenance a first-class,
non-optional property of every datum.

- **Every displayed number carries a source + timestamp**, exposed through the existing
  `/api/sources/{ticker}` mechanism and shown in the UI (hover/expand). Extend it to cover the
  new fields (trial depth, flow, comps, NMPA, private-entity data).
- **Freshness labels.** Show "as of" dates; flag stale (e.g. yfinance fundamentals, CCASS cold
  loads) rather than presenting them as live.
- **Never fabricate.** Missing data renders an explicit empty/"not available" state — never a
  zero, a default, or an inferred number presented as fact. (This is already the audit's P0
  standard; enforce it for all new fields.)
- **Assumptions visible.** Every computed valuation (rNPV, comps, any private-entity number)
  shows its assumptions inline, as rNPV already does.
- **AI outputs labeled.** All LLM-derived text keeps `ai_generated: true` and is visually
  marked, per existing governance.

---

## §5 — UI / UX & information design (the terminal has to *feel* institutional, not just contain the data)

A biotech PM decides in seconds whether a tool is credible. Right now the frontend is a
windowed desktop (`frontend/src`: `windowManager`, `panelRegistry`, `Desktop`, `Window`,
`TopBar`, `WindowsMenu`, `TickerInput`, `useIsDark`) with ~18 tab panels. The engine work in
§1–§4 adds many new panels; without a deliberate information-design pass they will accrete into
clutter. This section makes the interface itself trustworthy.

**First, a UX audit** (record findings, like the analytical audit did — repro or `file:line`):
walk the real loop — enter ticker → open every panel → move/resize/close/refocus → switch
tickers with panels open → invalid ticker → HK ticker → private entity → reload. Grade each
panel's **loading / empty / error / stale** states. Known debt to fix: CCASS ~38s cold load is
spinner-only (feels hung); several panels lack honest empty states; window state persistence and
refresh-on-ticker-change behavior are uneven.

**Design principles (from how institutional terminals are actually built):**

1. **Every pixel is accountable; hierarchy earned by importance, not decoration.** The one number
   that matters (price, or rNPV/share for a private co) is large and high-contrast at the top;
   secondary metrics are smaller and muted below. No chart-junk, no gratuitous color. Density is
   a feature — but *organized* density.
   ([Bloomberg UX](https://www.bloomberg.com/company/stories/how-bloomberg-terminal-ux-designers-conceal-complexity/),
   [The Skins Factory](https://www.theskinsfactory.com/uiux-design-blog/fintech-ui-ux-design))
2. **Conceal complexity, don't remove it.** Progressive disclosure: headline value first,
   assumptions/provenance one interaction away (hover/expand), full methodology behind that.
   This reconciles "institutional depth" with "not overwhelming."
3. **Keyboard-driven and predictable.** A command line / fuzzy launcher (ticker or company name,
   jump to any panel), consistent shortcuts, every panel a movable/pop-out pane. Predictability
   is the core Bloomberg navigation principle — the same action does the same thing everywhere.
   ([HN on dense UIs](https://news.ycombinator.com/item?id=19153875))
4. **Real-time readability is a trust signal.** Fast render, no layout shift, explicit
   "as of / stale" labels, skeleton loaders (not bare spinners) for slow loads like CCASS —
   delayed or janky data reads as a *trust-breaking* failure, not minor friction.
   ([Fintatech](https://fintatech.com/blog/how-ui-ux-design-impacts-financial-trading-performance/))
5. **Light + dark, both first-class and accessible.** Keep `useIsDark`; hold WCAG-AA contrast in
   both. Never encode meaning in color alone (colour-blind safe up/down); high-contrast numerics.
6. **State legibility for the new concepts.** The compliance layer needs unmistakable visual
   language: a **Restricted** badge, an MNPI banner, a private-vs-public entity marker, and a
   clear "AI-generated" mark — a user must never confuse a walled private note with a public
   signal, or an AI summary with sourced fact.
7. **Consistent panel contract.** Every panel — old and new — implements the same four states
   (loading skeleton / real data / honest empty / error) and the same header pattern
   (title · "as of" · source-link · optional AI badge). Codify this so §1–§4's new panels can't
   regress it.

**Do not** modify `index.html` or `assets/` by hand — this is compiled output. UX changes are
made in `frontend/src` and rebuilt; ship a fresh build so the served bundle matches the canonical
source (the audit already flagged a stale served bundle once).

**Acceptance:** the UX audit is written; a documented panel-state contract exists and every
panel (incl. new §1–§4 panels) conforms; CCASS and other slow loads show skeletons + progress,
not a bare spinner; a keyboard launcher jumps to any ticker/company/panel; Restricted / private /
AI-generated states are visually unmistakable; WCAG-AA contrast holds in light and dark; a fresh
build is served.

---

## Phased roadmap (ordered by trust-impact-per-effort; each phase has a testable deliverable)

Work top-down. Do not start a phase until the prior phase's acceptance test passes. All backend
routes are **additive** — never change an existing path or response field (compiled React
depends on them). New routes go before the static mount and SPA fallback in `server.py`.

- **Phase J — Compliance wall + private-note capture (foundational; unlocks everything private).**
  Build §0 end-to-end: note object + provenance + MNPI triage + personal restricted list +
  signal suppression + audit log. Deliverable: the §0 acceptance test passes. No private-capture
  UI ships before this test is green. Files: new `compliance.py`, `server.py` routes
  (`/api/notes`, `/api/restricted`), a Notes panel, `AI_GOVERNANCE.md` update.

- **Phase K — Private Company entity model (§1).** Entity resolution, private-entity data pulls
  (ClinicalTrials.gov + RePORTER + patents + EDGAR), rNPV-only valuation, funding/deal comps,
  data-room attachment. Deliverable: §1 acceptance test. Files: `entities/` or
  `PrivateCompanyAdapter`, `/api/company` routes, private-company panel set.

- **Phase L — Public-side institutional depth (§2).** Trial depth, 13F/insider/short flow,
  competitive landscape, deal comps. Deliverable: §2 acceptance test. Files: `pipeline_analyzer.py`,
  Ownership route/tab, new competitive-landscape route/tab, `data_fetcher.py` primitives.

- **Phase M — China / NMPA + cross-border (§3).** `ChinaExchangeAdapter`, NMPA status, extended
  dual-listing cross-regulator view. Deliverable: §3 acceptance test. Files: `exchanges/cn.py`,
  `exchanges/__init__.py`, `dual_listing.py`, DualListing tab.

- **Phase N — Provenance & credibility hardening (§4).** Extend `/api/sources`, freshness labels,
  assumptions everywhere, audit the new fields for fabrication. Deliverable: every new field is
  citation-backed; a "no fabricated numbers" test passes across §1–§3 fields.

- **Phase O — UI/UX & information design (§5).** UX audit of the real interaction loop; codify the
  four-state panel contract + header pattern and retrofit every panel to it; skeleton loaders and
  progress for slow loads (CCASS); keyboard/command launcher; unmistakable Restricted / private /
  AI-generated visual states; WCAG-AA in light + dark; ship a fresh build. Deliverable: §5
  acceptance test. Files: `frontend/src/components/*`, `panelRegistry.tsx`, `windowManager.tsx`,
  `TopBar.tsx`, new command-launcher component; rebuilt `assets/`.

Provenance (§4) is woven through every phase, and the §5 panel-state contract should be honored by
new panels as they are built in J–M — Phases N and O are the final hardening sweeps (data trust,
then interface trust), not the first introduction of those concerns.

---

## Non-negotiables

- **§0 first.** No private-information capture ships before the compliance wall's acceptance
  test is green. If forced to cut scope, cut features, never the wall.
- **No fabricated data.** Missing → explicit empty state, never a default presented as fact.
- **Additive routes only.** Never change existing route paths or response field names; new routes
  before the static mount / SPA fallback. Do not modify `index.html` or `assets/`.
- **Adapter layer intact.** All market data through `data_fetcher.py` primitives and the exchange
  adapters; LLM calls only in `llm_analysis.py`.
- **502 not 500** on upstream failure; sanitize NaN/Inf via `_to_json_safe`.
- **Depth over breadth on geography** — HK, US, China only this cycle.
- **Tests are part of "done"** — each phase ships with tests using real small fixtures (no mocked
  yfinance).

## Questions the builder must resolve before starting

1. **Persistence.** Notes, restricted list, private entities, and audit log need durable storage.
   Is a single-file/SQLite local store acceptable for now, or is multi-user/hosted required
   (which changes the auth and data-isolation model)?
2. **Private-entity data licensing.** ClinicalTrials.gov, RePORTER, USPTO, and EDGAR are free and
   redistributable. Funding-round data (PitchBook/Crunchbase-grade) is licensed and expensive —
   confirm whether to rely on user-entered rounds + press-release scraping for now, or budget for
   a paid feed later.
3. **Restricted-list scope.** When a name is restricted, suppress signals only, or also hide it
   from the watchlist/screener entirely? (Compliance-strict vs. usability.)
4. **NMPA source.** Confirm a specific credible, citable NMPA data source before building §3;
   if none is reliably machine-readable, §3 degrades to an honest manual/"not available" state.
