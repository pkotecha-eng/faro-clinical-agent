# FARO Review Notes — 2026-11-01

Working notes from a code review + live-repro debugging session (test case
`tc_001`: Pediatric Epilepsy, age 8). Each item below was traced in the
actual code and, where applicable, reproduced against the real APIs — not
inferred from the docs.

---

## Fixed and verified

### 1. Synthesizer never received the eligibility assessor's output

`tasks.py:150` built `synthesize_report` with `context=[]` whenever a
parallel-phase context string was supplied — which `crew.py` always does in
Phase 2. CrewAI's `_get_context()` (`crewai/crew.py:1734-1742` in the
installed package) treats an empty list the same as "no context from other
tasks," returning `""`. Since this is CrewAI's *only* mechanism for passing
one task's output into the next task's prompt in `Process.sequential`
(`crewai/crew.py:1473-1477`), the Patient Navigator was synthesizing reports
with zero visibility into the eligibility ratings it was instructed to
"follow strictly" — on every run, not just under failure.

**Fix:** `tasks.py:150` —
`context=[assess_eligibility] if context else [...]`, referencing the same
`assess_eligibility` `Task` object (confirmed identical by `id()`/`is`) that
runs immediately before it in Phase 2's `Crew`.

**Verified:** captured the synthesizer's actual prompt via
`AgentExecutionStartedEvent` on a post-fix run (no pre-fix prompt was
captured — this wasn't a before/after comparison). The prompt contains the
assessor's full per-trial output verbatim (`# ELIGIBILITY ASSESSMENT FOR
PEDIATRIC EPILEPSY TRIALS`, ratings, reasoning) under "This is the context
you're working with:". The synthesizer's captured prompt was 22,207 bytes,
versus the assessor's own 11,105-byte prompt — consistent with the full
assessor output being included rather than dropped.

### 2. Tool error dicts formatted as fake trial/paper records

`tools.py`'s three fetch functions catch exceptions and return
`[{"error": str(e)}]` — a non-empty list. `agents.py`'s three
`BaseTool._run()` methods only checked `if not results`, which is `False`
for a non-empty error-shaped list, so execution fell into the per-item
formatting loop and emitted a fake record with every field rendered as
`None` (e.g. `"NCT ID: None"`, `"Age Range: N/A to N/A"`) — indistinguishable
from real (if sparse) data to the downstream agent.

**Fix:** added `_tool_error()` (`agents.py:26-36`) and a check before the
existing `if not results` branch in all three wrappers
(`agents.py:54`, `78`, `116`), returning an explicit
`"Error searching <source>: <message>"` string instead.

**Verified:** mocked `search_pubmed`/`search_clinical_trials`/`search_isrctn`
to return the error shape; confirmed each wrapper now returns the explicit
error string, while genuinely empty results (`[]`) and real data are
unaffected (same output as before the fix).

### 3. PubMed fetch hardening (status/content-type validation + retry)

Root-caused via direct, non-concurrent, no-LLM reproduction (see below) to
transient non-200/non-XML responses from NCBI's eutils under request load —
not a bug in URL construction, `requests` usage, or `xmltodict` parsing
(confirmed: single isolated call and `curl` on the same `efetch` URL both
return identical, valid, 89,632-byte XML).

**Fix:** `tools.py:12-37` — new `_get_with_retry()` helper validates
`status_code == 200` and the expected `content-type` before returning;
retries twice (1s, then 2s backoff) on failure; on final failure raises
`RuntimeError` with status, content-type, and the first 200 chars of body,
which flows into the existing `except Exception as e: return [{"error":
str(e)}]` path. Applied to both `esearch` (`tools.py:51`, expects `json`)
and `efetch` (`tools.py:64`, expects `xml`).

**Repro before fix** (10 fixed queries, `search_pubmed` called directly, no
LLM):
- Single isolated call: 0/1 failures (confirmed both via Python `requests`
  and `curl` on the identical `efetch` URL — byte-identical response).
- 10 sequential calls, no sleep: **2/10** failed with
  `ExpatError: not well-formed (invalid token): line 1, column 0`.
- 10 queries across 10 concurrent threads: **3/10** failed, same error.
- Exactly 2 concurrent threads (5 queries each): **1/10** failed, same
  error.

**Repro after fix**, identical queries and thread patterns:
- 10 sequential, no sleep: **0/10** failures.
- Exactly 2 concurrent threads: **0/10** failures.

### 4. `esearch` returning empty results under load — mechanism unconfirmed

In the same stress test, several queries returned a clean "0 papers"
rather than an error — `beta thalassemia`, `levetiracetam`, `Prader-Willi
Syndrome`, and Congenital Adrenal Hyperplasia all came back empty despite
being well-indexed topics, consistent with `esearch` returning something
anomalous under load rather than `efetch` crashing.

**Observed after the fix:** the identical 10-query stress test (sequential
and 2-thread) returned real papers for every query, including all four
that previously came back empty.

**Do not read this as proven fixed.** `_get_with_retry` (`tools.py:15-37`)
only retries on a non-200 status or wrong content-type — it has no way to
detect or retry a *valid* 200 JSON response with a genuinely empty
`idlist`. So either (a) these particular empties actually were non-200/
non-JSON responses that the retry legitimately caught, or (b) the empties
disappeared because this rerun happened under different load/timing than
the original run, unrelated to the fix. Nothing captured distinguishes
the two. See Open item 8 below — a valid-but-empty throttle response is
exactly the failure mode this fix cannot catch, and that may be what
happened here.

---

## Open, in priority order

### 1. Section 2 presents unsourced claims when literature retrieval fails (#3b)

Even with PubMed now reliable in the common case, any future literature
failure still flows through uncontrolled. `tasks.py`'s `synthesize_report`
embeds `context_text` (trials + literature, raw) directly into its
description with no branching on whether literature actually succeeded.
Confirmed on the pre-fix tc_001 run: the Literature agent's honest failure
disclosure ("I apologize, I'm unable to retrieve...") reached Section 2,
but the Navigator's final text followed it with unsourced, un-cited claims
("drug-resistant focal epilepsy... treatment approaches being studied
include... ketogenic diet... neuromodulation devices") under a header
titled "WHAT THE RESEARCH SAYS" — content from the model's own parametric
knowledge, not from any retrieved source.

**Why it's not a one-line patch:** `crew.py` only ever sees the Literature
agent's *narrated* final answer (`lit_result`), not the tool's structured
return value — so it can't reliably detect "literature actually failed"
by string-matching prose that varies run to run. Needs a signal read off
the tool/agent object itself, which is blocked on the per-run tool state
item below.

### 2. Trials-abort: if all trial sources fail, raise before Phase 2

Today, if `search_clinical_trials` and `search_isrctn` both exhaust retries
and fail, `agents.py`'s wrappers now return an explicit error string
(fixed in #2 above) — but `crew.py:37-41` has no gate on `trials_result`
before building `combined_context` and proceeding into Phase 2. The
eligibility assessor and synthesizer would run against "Error searching..."
text as if it were trial data, and `app.py:150` would still report
`"Report ready!"` / `state="complete"`.

**Also blocked on** the per-run tool state item below — same reason as #1:
need a structured, deterministic signal, not prose-sniffing.

### 3. Per-run tool state: how `crew.py` reads this run's tool outcomes

`pubmed_tool`, `trials_tool`, `isrctn_tool` are module-level singletons
(`agents.py:101-102`, `139`), shared across every concurrent `run_faro()`
call and wired into agents at `agents.py:152` (`trials_tool`, `isrctn_tool`)
and `agents.py:166` (`pubmed_tool`). Any mechanism that records "did this
tool call succeed" as mutable state *on these shared instances* would race
across concurrent Streamlit sessions. This blocks both #1 and #2 above:
neither can be built correctly until tool instances are created per-run
(inside `create_agents()`, called fresh each `run_faro()` call) and expose
their structured results back to `crew.py`.

Two implementation paths, not decided yet — pick one next session:

**(a) Per-run tool instances with accumulating state.** Create tool
instances inside `create_agents()` and read them back via the `Agent.tools`
list after `kickoff()`, with no event bus and no cross-request
correlation needed. Important detail: the state must **accumulate every
call made during the agent's reasoning loop, not just overwrite with the
most recent one** — in the tc_001 trace, the Literature agent alone made 6
PubMed calls with 6 different queries, and the Trial Scout calls both
`ClinicalTrialsTool` and `ISRCTNTool`. A single-slot `last_results`
attribute would silently keep only the final call's outcome and drop the
other five. Needs a list that each `_run()` call appends to, not a scalar
that each call overwrites.

**(b) Direct Python retrieval + one Haiku call for query generation.**
Skip the retrieval agents' tool-calling loop entirely: have `crew.py` call
`search_clinical_trials`/`search_isrctn`/`search_pubmed` directly
(structured `list[dict]`, gate on that directly, no agent in between),
optionally preceded by a single Haiku call that generates 3-5 query
variations from the condition up front — preserving some of the
reformulation behavior the Literature agent currently provides on its own
(the 7-query trace from tc_001), without the full agentic retry loop.
`combined_context` would then be built from the real, structured tool
results, not from an agent's narrated final answer — removing the
agent's-prose-as-ground-truth problem for Phase 1 entirely, rather than
working around it.

Trade-off: (a) preserves full adaptive, context-aware reformulation
(each query informed by the previous result) at the cost of more
plumbing; (b) is simpler and strictly cheaper (fewer LLM calls, no
agentic loop to get stuck in) but reduces retrieval to whatever query
variations the one upfront Haiku call proposes, not adaptive reformulation.

### 4. `max_iter` / `max_execution_time` limits plus iteration check (#4)

No agent in `agents.py:141-180` sets `max_iter` or `max_execution_time`, so
all four default to `max_iter=25`
(`crewai/agents/agent_builder/base_agent.py:246` in the installed package).
If an agent hits that limit, `handle_max_iterations_exceeded()`
(`crewai/utilities/agent_utils.py:254-294`) forces one more LLM call for a
"final answer" and returns it as a normal `TaskOutput` — no exception, no
UI-visible signal, only a yellow console line that never reaches
`app.py` or Supabase. That forced-finish text would flow on as if complete.

**Not yet a factor in observed runs:** diagnostic instrumentation on tc_001
read `agent.agent_executor.iterations` vs `.max_iter` directly off the
`Agent` object after `kickoff()` — Trial Scout: 2/25, Literature
Researcher: 3/25. Confirmed accessible with no event bus (`Agent.agent_executor`
is a plain field, `agents/agent_builder/base_agent.py:301`) — same
read-an-attribute-off-an-object-we-already-hold pattern as the per-run tool
state item, just doesn't need the per-run-instance refactor since `Agent`
objects are already created fresh each call in `create_agents()`.

### 5. Eval upgrade

Current checks (`eval/run_eval.py:17-39`) are weaker than they look:
- `TRIAL_INDICATORS = ["NCT", "ISRCTN", "clinicaltrials.gov", "Phase",
  "Recruiting"]` (`eval/run_eval.py:28`) would false-positive on the
  pre-#2-fix garbage output (`"NCT ID: None"` contains `"NCT"`, `"Phase:
  None"` contains `"Phase"`) — i.e. the eval could have passed on a run
  where every trial source had silently failed.
- No check that NCT IDs appearing in the final report were ever actually
  fetched (an NCT-ID regex + fetched-vs-cited diff would catch both
  hallucinated IDs and the above false-positive class).
- No verdict-consistency check: for every trial, the rating stated in the
  final report (Section 4) must match the rating the assessor actually
  gave that same trial. Even with the context fix (item 1 above), nothing
  stops the synthesizer from restating a different verdict than the one
  it was handed — the fix guarantees the assessor's output *reaches* the
  synthesizer, not that the synthesizer's report *agrees* with it.
- No outage/failure test case — all 6 cases in `eval/test_cases.json`
  assume every API succeeds; nothing exercises the error paths we just
  hardened.

### 6. Retrieval: deterministic age pre-filter; CT.gov `StdAge` filter unverified

`search_clinical_trials` (`tools.py:116-128`) queries only on
`query.cond`/`query.intr`/`filter.overallStatus` — no age parameter exists
anywhere in the retrieval path, and `agents.py`'s `TrialsInput` schema
(tool-callable surface) only exposes `condition`. All age-appropriateness
filtering happens post-hoc in the eligibility assessor. On tc_001, this is
why a trial requiring ages 11–18 was fetched at all for an 8-year-old.

Checked (not from memory) whether ClinicalTrials.gov API v2 supports
server-side age filtering: confirmed `filter.advanced` with
`AREA[FieldName]RANGE[...]` syntax exists and works for other numeric/date
fields (`AREA[EnrollmentCount]RANGE[1000,MAX]`, `AREA[StartDate]RANGE[...]`,
per third-party references citing the official OpenAPI spec). Secondary
sources state `MinimumAge`/`MaximumAge`/`StdAge` exist as schema fields,
but **no source found — official or third-party — has a confirmed, worked
example of `AREA[StdAge]CHILD` or `AREA[MinimumAge]RANGE[...]` actually
filtering results.** CT.gov's own doc site is a JS-rendered SPA that
`WebFetch` could not execute, so this was not independently verified
against the live API. A Python-side post-filter on the already-returned
`min_age`/`max_age` fields is the verified-safe option regardless of what
the API supports.

### 7. Assessor treats unstated facts as "no" instead of "unknown → Possibly Eligible"

On tc_001, trial NCT07594652 requires an ADHD diagnosis. The patient
profile is epilepsy-focused and never mentions ADHD one way or the other —
an absent data point. The assessor wrote "no indication patient has ADHD"
and rated it Likely Ineligible, rather than flagging it as unknown and
defaulting to Possibly Eligible per `tasks.py:84-86` ("If a criterion
requires lab values, medication dates, or clinical measurements not
present in the patient profile... default to Possibly Eligible"). Note the
instruction's literal scope ("lab values, medication dates, or clinical
measurements") doesn't technically cover "undiagnosed comorbidity," so this
is partly an instruction-scope gap, not purely an assessor error — worth
fixing both the instruction and confirming the assessor follows it once
widened.

### 8. Undetected failure mode: `esearch` returning valid empty JSON under throttle

The retry/validation added in the PubMed hardening (#3 above) only retries
on non-200 or wrong-content-type. If NCBI ever returns a **valid 200 JSON
response with an empty `idlist`** as a throttling response (rather than a
non-200/non-JSON body, which is what we reproduced and fixed), `tools.py`
would treat it as a legitimate "no results" and return `[]` — indistinguishable
from a genuine zero-hit query. Not observed in this session's repro (every
throttle-shaped failure we triggered was non-200/non-JSON), but not ruled
out either, and the current fix cannot catch it.

### 9. Optional: NCBI API key, retry on request-level exceptions

An NCBI API key raises the unauthenticated ~3 req/sec eutils limit
(`TECHNICAL_REFERENCE.md:930-935` documents the current unauthenticated
limit) — would likely reduce how often the retry path in `tools.py` is
needed at all. Separately, `_get_with_retry` (`tools.py:15-37`) only
retries on a successfully-received bad response; it does not catch
`requests` exceptions (timeout, connection error) raised by `requests.get`
itself — those still propagate straight to the outer `except Exception`
in `search_pubmed` with no retry.

### 10. Hygiene

- Pin `crewai==1.14.2` in `requirements.txt:1` — currently unpinned
  (`crewai`, `crewai-tools` with no version), even though the installed
  venv version happens to match the README's claim today.
- `TECHNICAL_REFERENCE.md` is stale in several places found this session:
  - §4.2/§11/Appendix (`TECHNICAL_REFERENCE.md:407`, `1059`, and the
    "Web Application" section) claim the synthesizer "reads eligibility
    output via CrewAI sequential context" — this was false prior to
    today's fix (item 1 above) and the prose should be updated to describe
    the actual mechanism now in place.
  - §13 (`TECHNICAL_REFERENCE.md:818`) says "Four test scenarios" —
    `eval/test_cases.json` has 6 (tc_005, tc_006 added in a prior commit,
    doc never updated).
  - §8.2 (`TECHNICAL_REFERENCE.md:623`) documents the no-exclusion-marker
    branch as truncating inclusion criteria to `[:600]`; the actual code
    (pre- and post- this session's changes, unaffected by today's edits)
    truncates to `[:400]`.
  - §12 documents `log_eval_run` (`db.py:78`) as if it's part of the active
    eval-logging flow; it's defined but has zero call sites anywhere in
    the codebase (`eval/run_eval.py` never calls it) — dead code, doc
    should say so or the call should be wired in.
- Move today's diagnostic/capture scripts
  (`capture_prompt.py`, `diagnose_pubmed.py`, currently in the session
  scratchpad) into `eval/` if they're worth keeping as reusable diagnostic
  tooling rather than one-off scratch files.
