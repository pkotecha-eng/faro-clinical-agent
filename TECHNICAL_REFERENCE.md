# FARO Clinical Agent — Technical Reference

> **Stack:** Python 3.12 · CrewAI · Claude (claude-sonnet-4-5 / claude-haiku-4-5) · Streamlit · Supabase · Fly.io

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Project Structure](#2-project-structure)
3. [Installation & Entry Points](#3-installation--entry-points)
4. [Orchestration (`crew.py`)](#4-orchestration-crewpy)
   - [Parallel Phase](#41-parallel-phase)
   - [Sequential Phase](#42-sequential-phase)
5. [Agents (`agents.py`)](#5-agents-agentspy)
   - [Trial Scout](#51-trial-scout)
   - [Literature Researcher](#52-medical-literature-researcher)
   - [Eligibility Assessor](#53-trial-eligibility-specialist)
   - [Patient Navigator (Synthesizer)](#54-patient-care-navigator-synthesizer)
6. [Tasks (`tasks.py`)](#6-tasks-taskspy)
   - [Task 1 — Find Trials](#61-task-1--find-trials)
   - [Task 2 — Search Literature](#62-task-2--search-literature)
   - [Task 3 — Assess Eligibility](#63-task-3--assess-eligibility)
   - [Task 4 — Synthesize Report](#64-task-4--synthesize-report)
7. [CrewAI Tool Wrappers (`agents.py`)](#7-crewai-tool-wrappers-agentspy)
   - [PubMedTool](#71-pubmedtool)
   - [ClinicalTrialsTool](#72-clinicaltrialstool)
   - [ISRCTNTool](#73-isrctntool)
8. [Internal Data Layer (`tools.py`)](#8-internal-data-layer-toolspy)
   - [PubMed Pipeline](#81-pubmed-pipeline)
   - [ClinicalTrials.gov Pipeline](#82-clinicaltrialsgov-pipeline)
   - [ISRCTN Pipeline](#83-isrctn-pipeline)
9. [Data Models](#9-data-models)
10. [Report Format](#10-report-format)
11. [Web Application (`app.py`)](#11-web-application-apppy)
12. [Database Layer (`db.py`)](#12-database-layer-dbpy)
13. [Evaluation Framework (`eval/`)](#13-evaluation-framework-eval)
14. [Error Handling](#14-error-handling)
15. [Rate Limits & Constraints](#15-rate-limits--constraints)
16. [Deployment](#16-deployment)
17. [Dependencies](#17-dependencies)
18. [Environment Variables](#18-environment-variables)

---

## 1. Architecture Overview

```
User (browser)
      │  HTTP
      ▼
┌─────────────────────────────────────────────────────────────────┐
│  app.py  — Streamlit web application                            │
│  Input form → run_faro(condition, patient_profile) → report     │
│  Session logging → Supabase via db.py                           │
└─────────────────────────────┬───────────────────────────────────┘
                              │ Python call
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  crew.py  — Orchestration layer (run_faro)                      │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Phase 1: PARALLEL (ThreadPoolExecutor, max_workers=2)   │   │
│  │   Agent 1: Trial Scout       → find_trials task         │   │
│  │   Agent 2: Literature Agent  → search_literature task   │   │
│  └────────────────────────┬────────────────────────────────┘   │
│                           │ combined_context string             │
│  ┌────────────────────────▼────────────────────────────────┐   │
│  │ Phase 2: SEQUENTIAL (CrewAI Process.sequential)         │   │
│  │   Agent 3: Eligibility Assessor → assess_eligibility    │   │
│  │   Agent 4: Patient Navigator    → synthesize_report     │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────┬───────────────────────────────────┘
                              │ tool calls
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  agents.py — CrewAI tool wrappers                               │
│  PubMedTool     ClinicalTrialsTool     ISRCTNTool               │
└──────────┬───────────────┬──────────────────┬───────────────────┘
           │               │                  │
           ▼               ▼                  ▼
┌──────────────┐  ┌──────────────────┐  ┌────────────────────┐
│  tools.py    │  │  tools.py        │  │  tools.py          │
│  search_     │  │  search_clinical │  │  search_isrctn()   │
│  pubmed()    │  │  _trials()       │  │                    │
└──────┬───────┘  └────────┬─────────┘  └─────────┬──────────┘
       │                   │                       │  HTTP (requests)
       ▼                   ▼                       ▼
┌────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ NCBI PubMed    │  │ ClinicalTrials   │  │ ISRCTN Registry  │
│ E-utilities    │  │ .gov API v2      │  │ WHO-format XML   │
│ (XML)          │  │ (JSON)           │  │ API              │
└────────────────┘  └──────────────────┘  └──────────────────┘
```

All three upstream APIs are **public and zero-authentication**. No API keys are stored for data retrieval.

---

## 2. Project Structure

```
faro-clinical-agent/
├── app.py            # Streamlit web application (UI + session logging)
├── crew.py           # Orchestration: parallel + sequential agent runs
├── agents.py         # Agent definitions + CrewAI tool wrapper classes
├── tasks.py          # Task definitions (descriptions, expected outputs, agent assignment)
├── tools.py          # Raw HTTP clients + parsers for PubMed, CT.gov, ISRCTN
├── db.py             # Supabase client — session logging, eval tracking, memory retrieval
├── prompts.py        # (reserved — currently empty)
├── requirements.txt  # Runtime dependencies
├── Dockerfile        # Container build for Fly.io
├── fly.toml          # Fly.io deployment config
├── eval/
│   ├── run_eval.py   # Integration test runner
│   ├── test_cases.json  # Test case definitions (4 disease scenarios)
│   ├── results.json  # Latest eval run output
│   └── results.json.old
└── README.md
```

---

## 3. Installation & Entry Points

```bash
git clone https://github.com/pkotecha-eng/faro-clinical-agent
cd faro-clinical-agent
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Add credentials to `.env`:

```
ANTHROPIC_API_KEY=your_key_here
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key
```

Run the app:

```bash
streamlit run app.py
```

Run the eval suite:

```bash
python eval/run_eval.py
```

Run the orchestration layer directly (without UI):

```bash
python crew.py
# Executes the built-in __main__ block with a pediatric epilepsy test case
```

---

## 4. Orchestration (`crew.py`)

`run_faro(condition, patient_profile)` is the single public entry point. It wires together agents, tasks, and execution strategy.

```python
def run_faro(condition: str, patient_profile: str) -> str
```

| Parameter        | Type  | Description                                       |
|------------------|-------|---------------------------------------------------|
| `condition`      | `str` | Medical condition or diagnosis                    |
| `patient_profile`| `str` | Assembled patient context string                  |

**Returns:** Complete report as a markdown-formatted string.

### 4.1 Parallel Phase

```python
with ThreadPoolExecutor(max_workers=2) as executor:
    future_trials = executor.submit(run_task, find_trials, trial_scout)
    future_lit    = executor.submit(run_task, search_literature, literature_agent)
    trials_result = future_trials.result()
    lit_result    = future_lit.result()
```

Each parallel worker wraps one agent + one task in its own `Crew(process=Process.sequential)` instance and calls `crew.kickoff()`. Results are collected as plain strings.

> **Why parallel here?** Trial search and literature search are fully independent — neither needs the other's output. Running them concurrently reduces wall-clock time by ~40–60%.

### 4.2 Sequential Phase

After the parallel phase completes, the two results are merged into a single string:

```python
combined_context = f"TRIALS FOUND:\n{trials_result}\n\nLITERATURE:\n{lit_result}"
```

`create_tasks` is called a **second time** with `context=combined_context`. This injects the parallel results directly into the task descriptions for agents 3 and 4, bypassing CrewAI's built-in task-context chaining (which cannot cross independently-keyed Crew instances).

```
Crew([eligibility_assessor, synthesizer],
     [assess_eligibility_task, synthesize_report_task],
     Process.sequential)
     .kickoff()
```

The synthesizer's output becomes the final report returned to `app.py`.

---

## 5. Agents (`agents.py`)

All agents are constructed by `create_agents()` using `crewai.Agent`. Two LLM tiers are used:

| LLM handle | Model ID                     | Used by                        |
|------------|------------------------------|--------------------------------|
| `claude`   | `claude-sonnet-4-5`          | All four agents                |
| `haiku`    | `claude-haiku-4-5-20251001`  | Defined, not currently assigned|

All agents have `allow_delegation=False` (no inter-agent tool handoff).

---

### 5.1 Trial Scout

```python
Agent(
    role="Clinical Trial Scout",
    goal="Find the most relevant recruiting clinical trials for the patient's condition",
    tools=[trials_tool, isrctn_tool],   # ClinicalTrialsTool + ISRCTNTool
    llm=claude,
)
```

**Backstory:** Expert clinical trial coordinator with 10 years of ClinicalTrials.gov experience. Specializes in matching patient profiles against inclusion/exclusion criteria.

**Tools:** `ClinicalTrialsTool` (US-focused), `ISRCTNTool` (UK/Europe)

---

### 5.2 Medical Literature Researcher

```python
Agent(
    role="Medical Literature Researcher",
    goal="Find and summarize the latest published evidence for the patient's condition",
    tools=[pubmed_tool],   # PubMedTool
    llm=claude,
)
```

**Backstory:** Biomedical researcher specializing in synthesizing peer-reviewed PubMed literature. Explains findings in plain language accessible to patients and caregivers.

**Tools:** `PubMedTool`

---

### 5.3 Trial Eligibility Specialist

```python
Agent(
    role="Trial Eligibility Specialist",
    goal="Assess whether the patient likely qualifies for each trial found",
    tools=[],   # No external tools — operates on injected context
    llm=claude,
)
```

**Backstory:** Clinical trial eligibility specialist with experience reviewing thousands of patient profiles against trial criteria. Provides honest, plain-language assessments; always notes that final eligibility must be confirmed with the trial site.

**Tools:** None. Operates entirely on context injected via the task description.

---

### 5.4 Patient Care Navigator (Synthesizer)

```python
Agent(
    role="Patient Care Navigator",
    goal="Create a clear, compassionate, actionable report for the patient and their doctor",
    tools=[],   # No external tools — operates on injected context
    llm=claude,
)
```

**Backstory:** Patient navigator who bridges complex medical research and patients seeking help. Synthesizes findings into a structured report the patient can bring to their doctor. Writes with empathy, clarity, and hope.

**Tools:** None. Operates entirely on context injected via the task description.

---

## 6. Tasks (`tasks.py`)

All tasks are constructed by `create_tasks(agents, condition, patient_profile, context=None)`.

`context` is `None` in Phase 1 (parallel) and a pre-built `combined_context` string in Phase 2 (sequential). This switches between two wiring modes:

| `context` value | Task wiring mode                                                |
|-----------------|-----------------------------------------------------------------|
| `None`          | CrewAI task-reference chaining (`context=[find_trials, ...]`)  |
| string          | Injected directly into the task `description` field            |

---

### 6.1 Task 1 — Find Trials

**Assigned to:** Trial Scout

**Runs:** Parallel Phase (independently)

**Description instructs the agent to:**
- Use **both** `Search Clinical Trials` and `Search ISRCTN` tools
- Find up to 5 recruiting trials total across both registries
- Capture: Trial ID (NCT or ISRCTN), title, phase, sponsor, eligibility criteria (full), locations/countries, URL, primary outcome
- Note which registry each trial came from

**Expected output:**
> Detailed list of up to 5 recruiting trials from ClinicalTrials.gov and/or ISRCTN, with trial IDs, phases, sponsors, eligibility criteria, locations, primary outcomes, and URLs. Each trial notes its source registry.

---

### 6.2 Task 2 — Search Literature

**Assigned to:** Medical Literature Researcher

**Runs:** Parallel Phase (independently)

**Description instructs the agent to:**
- Use the `Search PubMed` tool
- Find up to 5 relevant papers
- Capture: title, authors, journal, year, key findings, URL
- Prioritize recent studies (last 3 years), treatment options, and promising interventions

**Expected output:**
> Summary of up to 5 peer-reviewed papers with titles, authors, journals, years, key findings, and PubMed URLs.

---

### 6.3 Task 3 — Assess Eligibility

**Assigned to:** Trial Eligibility Specialist

**Runs:** Sequential Phase (after parallel phase)

**Context source:** `combined_context` string (trials + literature results from Phase 1)

**Description instructs the agent to:**
For each trial found:
1. State the trial ID and title
2. List key inclusion criteria and whether the patient likely meets them
3. List key exclusion criteria and flag any potential disqualifiers
4. Rate eligibility: **Likely Eligible** / **Possibly Eligible** / **Likely Ineligible**
5. Explain reasoning in plain language
6. Always note that final eligibility must be confirmed with the trial site

**Expected output:**
> Eligibility assessment for each trial with ratings and plain-language reasoning.

---

### 6.4 Task 4 — Synthesize Report

**Assigned to:** Patient Care Navigator

**Runs:** Sequential Phase (last — receives Task 3's output via CrewAI context)

**Description instructs the agent to:**
Produce a full structured report with the sections below. Language rules are embedded in the task description:
- Define any medical term used, immediately in plain English in parentheses
- Section 0 must contain **zero medical jargon** — no exceptions
- Write with empathy, clarity, and hope
- Today's date is injected into the task description at runtime (`date.today().strftime('%B %d, %Y')`)

**Expected output:**
> Complete well-structured patient report with all 8 sections (0–7), in plain language a patient can bring to their doctor.

---

## 7. CrewAI Tool Wrappers (`agents.py`)

CrewAI agents cannot call raw Python functions directly — they require `BaseTool` subclasses with Pydantic input schemas. Three wrappers are defined in `agents.py`.

### 7.1 `PubMedTool`

```python
class PubMedTool(BaseTool):
    name: str = "Search PubMed"
    description: str = "Search PubMed for peer-reviewed biomedical literature on a condition or treatment."
    args_schema: type[BaseModel] = PubMedInput
```

**Input schema:**

| Field   | Type  | Required | Description              |
|---------|-------|----------|--------------------------|
| `query` | `str` | ✅        | PubMed search query      |

**Calls:** `tools.search_pubmed(query=query, max_results=5)`

**Returns:** Formatted string of up to 5 papers; `"No papers found."` on empty result.

---

### 7.2 `ClinicalTrialsTool`

```python
class ClinicalTrialsTool(BaseTool):
    name: str = "Search Clinical Trials"
    description: str = "Search ClinicalTrials.gov for recruiting trials for a given condition."
    args_schema: type[BaseModel] = TrialsInput
```

**Input schema:**

| Field       | Type  | Required | Description                      |
|-------------|-------|----------|----------------------------------|
| `condition` | `str` | ✅        | Medical condition to search for  |

**Calls:** `tools.search_clinical_trials(condition=condition, status="RECRUITING", max_results=5)`

**Returns:** Formatted string of up to 5 trials; `"No trials found."` on empty result.

---

### 7.3 `ISRCTNTool`

```python
class ISRCTNTool(BaseTool):
    name: str = "Search ISRCTN"
    description: str = "Search ISRCTN registry for UK and European clinical trials not listed on ClinicalTrials.gov."
    args_schema: type[BaseModel] = ISRCTNInput
```

**Input schema:**

| Field   | Type  | Required | Description                              |
|---------|-------|----------|------------------------------------------|
| `query` | `str` | ✅        | Condition or search terms for ISRCTN     |

**Calls:** `tools.search_isrctn(query=query, max_results=5)`

**Returns:** Formatted string of up to 5 trials; `"No ISRCTN trials found."` on empty result.

---

## 8. Internal Data Layer (`tools.py`)

`tools.py` contains all raw HTTP clients, XML/JSON parsers, and field extractors. It is called only by the CrewAI tool wrappers in `agents.py`. The three functions here are **identical in origin** to those in `aria-mcp-server/tools.py`, adapted for direct Python use (no MCP formatting layer).

### 8.1 PubMed Pipeline

**Base URL:** `https://eutils.ncbi.nlm.nih.gov/entrez/eutils`

**Two-step fetch pattern:**

```
GET esearch.fcgi?db=pubmed&term=<query>&retmax=<n>&retmode=json
    → idlist of PMIDs

GET efetch.fcgi?db=pubmed&id=<comma-sep PMIDs>&retmode=xml
    → PubmedArticleSet XML  (parsed with xmltodict)
```

**Key parsing logic:**

| Field           | Source XML path                                              | Notes                                      |
|-----------------|--------------------------------------------------------------|--------------------------------------------|
| `title`         | `MedlineCitation.Article.ArticleTitle`                      |                                            |
| `authors`       | `MedlineCitation.Article.AuthorList.Author[]`               | First 3; `"LastName ForeName"` format      |
| `journal`       | `MedlineCitation.Article.Journal.Title`                     |                                            |
| `year`          | `Journal.JournalIssue.PubDate.Year` or `MedlineDate[:4]`    |                                            |
| `abstract`      | `Article.Abstract.AbstractText`                             | Handles str, list, or dict with `#text` key|
| `pmid`          | `MedlineCitation.PMID.#text`                                |                                            |
| `url`           | `https://pubmed.ncbi.nlm.nih.gov/<pmid>/`                   | Constructed                                |

**Abstract truncation:** `abstract[:500]` in the tool wrapper display (first 500 chars shown to agent).

---

### 8.2 ClinicalTrials.gov Pipeline

**Base URL:** `https://clinicaltrials.gov/api/v2/studies`

**Response format:** JSON

**Query parameters:**

| CT.gov param           | Value                                |
|------------------------|--------------------------------------|
| `query.cond`           | `condition`                          |
| `query.intr`           | `intervention` (empty string = omit) |
| `filter.overallStatus` | `status` (default `"RECRUITING"`)    |
| `pageSize`             | `max_results`                        |
| `format`               | `"json"` (hardcoded)                 |

**Modules parsed from `protocolSection`:**

| Module key                      | Fields extracted                                                              |
|---------------------------------|-------------------------------------------------------------------------------|
| `identificationModule`          | `nctId`, `briefTitle`                                                         |
| `statusModule`                  | `overallStatus`                                                               |
| `designModule`                  | `phases` (list, joined as `", "`)                                             |
| `descriptionModule`             | `briefSummary`                                                                |
| `eligibilityModule`             | `eligibilityCriteria` (first 600 chars shown to agent), `minimumAge`, `maximumAge`|
| `sponsorCollaboratorsModule`    | `leadSponsor.name`                                                            |
| `conditionsModule`              | `conditions` (joined)                                                         |
| `contactsLocationsModule`       | `locations[]` — first 3 as `"city, country"` strings                         |
| `outcomesModule`                | `primaryOutcomes[0].measure` (≤300 chars), `secondaryOutcomes[:3]` (≤300 chars)|

---

### 8.3 ISRCTN Pipeline

**Base URL:** `https://www.isrctn.com/api/query/format/who`

**Response format:** WHO-standard XML (parsed with `xmltodict`)

**Relevance filter:** After the API response is parsed, a post-filter is applied to remove off-topic results:

```python
significant_words = [w for w in query_words if len(w) > 3]
if not any(word in searchable for word in significant_words):
    continue   # skip this trial
```

`searchable` = `f"{public_title} {hc_freetext}".lower()`. The filter requires at least one significant query word (>3 chars) to appear in the trial title or condition text.

**XML structure accessed:**

| XML path                        | Maps to field              | Notes                     |
|---------------------------------|----------------------------|---------------------------|
| `main.trial_id`                 | `trial_id`                 |                           |
| `main.public_title`             | `title`                    |                           |
| `main.recruitment_status`       | `status`                   |                           |
| `main.phase`                    | `phase`                    |                           |
| `main.primary_sponsor`          | `sponsor`                  |                           |
| `main.hc_freetext`              | `condition`                |                           |
| `main.url`                      | `url`                      |                           |
| `primary_outcome.prim_outcome`  | `primary_outcome`          | Truncated to 300 chars    |
| `countries.country2`            | `countries`                | List or str normalised    |
| `criteria.inclusion_criteria`   | `eligibility_criteria`     | Truncated to 400 chars    |
| `criteria.agemin`               | `min_age`                  |                           |
| `criteria.agemax`               | `max_age`                  |                           |
| `criteria.gender`               | `gender`                   |                           |

**Over-fetch:** The API is called with `limit = max_results * 2` to ensure enough results survive the relevance filter.

---

## 9. Data Models

### PubMed article dict (returned by `search_pubmed`)

```python
{
    "title":   str,          # Article title
    "authors": list[str],    # First 3: ["Last First", …]
    "journal": str,          # Journal name
    "year":    str,          # Publication year (4-char string)
    "abstract":str,          # Full abstract text (truncated to 500 in wrapper)
    "url":     str,          # https://pubmed.ncbi.nlm.nih.gov/<pmid>/
}
```

### ClinicalTrials.gov trial dict (returned by `search_clinical_trials`)

```python
{
    "nct_id":               str,        # NCT identifier
    "title":                str,        # Brief title
    "status":               str,        # e.g. RECRUITING
    "phase":                str,        # e.g. "PHASE2, PHASE3"
    "sponsor":              str,        # Lead sponsor name
    "conditions":           str,        # Comma-joined condition list
    "brief_summary":        str,        # Full brief summary
    "eligibility_criteria": str,        # Full eligibility text (truncated to 600 in wrapper)
    "min_age":              str,
    "max_age":              str,
    "locations":            list[str],  # First 3: "city, country"
    "url":                  str,        # https://clinicaltrials.gov/study/<nct_id>
    "primary_outcome":      str,        # Truncated to 300 chars
    "secondary_outcomes":   str,        # First 3, "; "-joined, truncated to 300 chars
}
```

### ISRCTN trial dict (returned by `search_isrctn`)

```python
{
    "trial_id":             str,        # ISRCTN identifier
    "title":                str,        # Public title
    "status":               str,        # e.g. Ongoing, Completed
    "phase":                str,
    "sponsor":              str,        # Primary sponsor
    "condition":            str,        # hc_freetext free text
    "primary_outcome":      str,        # Truncated to 300 chars
    "countries":            list[str],
    "min_age":              str,
    "max_age":              str,
    "gender":               str,
    "eligibility_criteria": str,        # Inclusion criteria, truncated to 400 chars
    "url":                  str,
}
```

---

## 10. Report Format

The synthesizer (Task 4) is instructed to produce a report with exactly 8 sections numbered 0–7. These section headers are also used by the eval framework to check completeness.

| # | Section heading                | Purpose                                                                   |
|---|--------------------------------|---------------------------------------------------------------------------|
| 0 | WHAT THIS MEANS FOR YOU        | 3–4 sentence plain-English summary. **Zero medical jargon.** Patient-first. |
| 1 | PATIENT SUMMARY                | Brief restatement of the patient's situation                              |
| 2 | WHAT THE RESEARCH SAYS         | Plain-language PubMed findings summary                                    |
| 3 | CLINICAL TRIALS MATCHED        | Trials ranked by eligibility fit, with IDs, URLs, primary outcomes        |
| 4 | ELIGIBILITY ASSESSMENT         | Per-trial rating + key reasons                                            |
| 5 | QUESTIONS TO ASK YOUR DOCTOR   | 3–5 specific questions based on the findings                              |
| 6 | NEXT STEPS                     | Concrete actions the patient can take                                     |
| 7 | IMPORTANT DISCLAIMER           | Informational use only; consult healthcare team                           |

**Post-processing in `app.py`:** After the report is returned, `app.py` injects the current date as a subheading after the report's `# ` title line, and appends an educational disclaimer blockquote.

---

## 11. Web Application (`app.py`)

Single-file Streamlit app. No backend server — Streamlit serves it directly.

### Session flow

```
Page load
  → st.session_state.session_id = uuid4()

User fills form + clicks "Generate My Report"
  → _build_patient_profile() assembles patient_profile string
  → log_session() → Supabase (condition, patient_type, session_id)
  → run_faro(condition, patient_profile) [blocking; 2–3 min]
  → update_session_report_generated(session_id) → Supabase
  → Report rendered as markdown
  → Download button renders (txt file)
  → log_download() on click → Supabase
```

### Form fields

| Field                              | Streamlit widget   | Maps to                               |
|------------------------------------|--------------------|---------------------------------------|
| Medical condition or diagnosis *   | `text_input`       | `condition` (required)                |
| Age                                | `text_input`       | `patient_profile` part                |
| Location (optional)                | `text_input`       | `patient_profile` part                |
| Treatments already tried           | `text_area`        | `patient_profile` part                |
| Other relevant medical information | `text_area`        | `patient_profile` part                |
| Real situation / Testing the tool  | `radio`            | `patient_type` (logged to Supabase)   |

### `_build_patient_profile`

Assembles the `patient_profile` string from optional fields:

```python
parts = []
if age:             parts.append(f"Age: {age}")
if location:        parts.append(f"Location: {location}")
if treatments_tried:parts.append(f"Treatments tried: {treatments_tried}")
if other_info:      parts.append(f"Additional information: {other_info}")
return ". ".join(parts) or "No additional profile information provided."
```

---

## 12. Database Layer (`db.py`)

Supabase is used for **session telemetry** and **eval run logging**. Connection is lazy — a client is instantiated per call via `get_client()`.

### `faro_sessions` table

| Column              | Type      | Set when                                |
|---------------------|-----------|-----------------------------------------|
| `session_id`        | `uuid`    | Page load (uuid4)                       |
| `condition`         | `text`    | Form submit                             |
| `patient_profile`   | `text`    | Form submit (empty string, not used)    |
| `patient_type`      | `text`    | Form submit radio value                 |
| `report_generated`  | `bool`    | `update_session_report_generated()`     |
| `report_downloaded` | `bool`    | `update_session_downloaded()`           |

### `faro_eval_runs` table

| Column                  | Type        | Description                                 |
|-------------------------|-------------|---------------------------------------------|
| `condition`             | `text`      | Test case condition                         |
| `faro_version`          | `text`      | Version tag for the eval run                |
| `retrieval_precision`   | `float`     | Fraction of expected trials found           |
| `sections_complete`     | `int`       | Count of present sections (0–7)             |
| `section_0_jargon_free` | `bool`      | Manual or LLM-graded jargon check           |
| `trial_ids_found`       | `text[]`    | List of NCT/ISRCTN IDs found in report      |
| `report_word_count`     | `int`       | Word count of final report                  |

### `get_past_searches` (memory layer)

```python
def get_past_searches(condition: str, limit: int = 5) -> list
```

Retrieves past sessions for the same condition where `report_generated = True`. Designed as a future memory/context layer — not yet wired into the agent pipeline.

### Error handling

All Supabase functions catch `Exception`, print to stdout, and return empty defaults. Supabase failures never surface to the user — they degrade silently.

---

## 13. Evaluation Framework (`eval/`)

### Test cases (`test_cases.json`)

Four test scenarios covering rare/complex conditions:

| ID       | Condition                           | Age  | Location    |
|----------|-------------------------------------|------|-------------|
| `tc_001` | Pediatric Epilepsy                  | 8    | New York    |
| `tc_002` | Beta Thalassemia                    | 28   | New Jersey  |
| `tc_003` | Classic Congenital Adrenal Hyperplasia | 6 | New York    |
| `tc_004` | Prader-Willi Syndrome               | 12   | New York    |

### Eval checks (`run_eval.py`)

Each test case is run through `run_faro()` and evaluated on three automated dimensions:

| Check              | Method                                                          | Passes when                              |
|--------------------|-----------------------------------------------------------------|------------------------------------------|
| `trial_found`      | Any of `["NCT", "ISRCTN", "clinicaltrials.gov", "Phase", "Recruiting"]` in report | At least one indicator present |
| `min_length`       | `len(report) >= 1000`                                           | Report is substantive                    |
| `sections`         | Each of the 8 section headers present as substring             | All 8 sections found                     |

**Overall pass criterion:**
```python
result["passed"] = (
    completed
    and trial_found
    and min_length
    and all(sections.values())
)
```

### Output (`results.json`)

```json
{
  "run_at": "2026-05-21T...",
  "summary": { "passed": N, "total": N },
  "results": [
    {
      "id": "tc_001",
      "condition": "...",
      "timestamp": "...",
      "completed": true,
      "checks": {
        "trial_found": true,
        "min_length": true,
        "sections": { "0. WHAT THIS MEANS FOR YOU": true, ... }
      },
      "passed": true,
      "report": "..."
    }
  ]
}
```

> **Note:** `run_eval.py` line 103 currently hard-filters to `tc_004` only: `test_cases = [tc for tc in test_cases if tc["id"] in ("tc_004")]`. Remove or adjust this filter to run all cases.

---

## 14. Error Handling

### Data layer (`tools.py`)

All three functions wrap their logic in `try/except Exception as e: return [{"error": str(e)}]`. An error result is a list containing a single dict with only an `"error"` key — the CrewAI tool wrappers pass this string to the agent, which treats it as empty/unavailable data.

### CrewAI tool wrappers (`agents.py`)

Return `"No papers found."` / `"No trials found."` / `"No ISRCTN trials found."` when the underlying function returns an empty list.

### Web app (`app.py`)

The entire `run_faro()` call is wrapped in a `try/except`. On failure:
```python
status.update(label="Error occurred", state="error")
st.error(f"Something went wrong: {e}. Please try again.")
```
No stack trace is shown to the user.

### Database layer (`db.py`)

All Supabase operations catch `Exception`, print to stdout, and return empty defaults. Never propagates to the UI.

---

## 15. Rate Limits & Constraints

| Source                | Rate limit                       | Auth required | `max_results` cap |
|-----------------------|----------------------------------|---------------|-------------------|
| NCBI E-utilities      | ~3 req/sec (unauthenticated)     | No            | 5 (tool wrapper)  |
| ClinicalTrials.gov v2 | Not publicly documented          | No            | 5 (tool wrapper)  |
| ISRCTN Registry       | Not publicly documented          | No            | 5 (tool wrapper)  |
| Anthropic API         | Depends on tier                  | Yes (API key) | —                 |

All tool wrappers hard-code `max_results=5`. The underlying `tools.py` functions accept any integer.

**Timeouts:** All `requests.get` calls use `timeout=10` (PubMed esearch, CT.gov) or `timeout=15` (ISRCTN).

---

## 16. Deployment

### Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8501
CMD ["streamlit", "run", "app.py",
     "--server.port=8501",
     "--server.address=0.0.0.0",
     "--server.headless=true"]
```

### Fly.io

```toml
app = 'faro-clinical-agent'
primary_region = 'ewr'         # Newark, NJ

[http_service]
  internal_port = 8501
  force_https = true
  auto_stop_machines = 'stop'
  auto_start_machines = true
  min_machines_running = 0     # Scale to zero when idle

[[vm]]
  memory = '1gb'
  cpu_kind = 'shared'
  cpus = 1
```

`min_machines_running = 0` means the app scales to zero between runs. First-request cold-start adds ~5–10 seconds before Streamlit serves.

**Deploy:**

```bash
fly deploy
fly secrets set ANTHROPIC_API_KEY=your_key
fly secrets set SUPABASE_URL=your_url
fly secrets set SUPABASE_KEY=your_key
```

---

## 17. Dependencies

| Package          | Role                                                          |
|------------------|---------------------------------------------------------------|
| `crewai`         | Multi-agent orchestration framework (agents, tasks, crews)    |
| `crewai-tools`   | `BaseTool` base class for CrewAI-compatible tool wrappers     |
| `anthropic`      | Anthropic Python SDK (pulled in by CrewAI for Claude LLMs)    |
| `streamlit`      | Web UI framework                                              |
| `requests`       | HTTP client for PubMed, ClinicalTrials.gov, ISRCTN APIs       |
| `xmltodict`      | XML→dict parser for PubMed and ISRCTN XML responses           |
| `python-dotenv`  | `.env` file loading                                           |
| `supabase`       | Supabase Python client for session and eval logging           |

---

## 18. Environment Variables

| Variable          | Required | Used by          | Description                              |
|-------------------|----------|------------------|------------------------------------------|
| `ANTHROPIC_API_KEY` | ✅     | `agents.py`      | Claude API access (Sonnet + Haiku)       |
| `SUPABASE_URL`    | ✅        | `db.py`          | Supabase project URL                     |
| `SUPABASE_KEY`    | ✅        | `db.py`          | Supabase anon/service key                |
| `OPENAI_API_KEY`  | ⚠️       | `crew.py`        | Set to `"NA"` — dummy to satisfy CrewAI internal checks. Do not provide a real key. |

---

## Appendix: Full Data Flow — Single User Request

```
User submits form: condition="Prader-Willi Syndrome", age="12", location="New York"
        │
        ▼ app.py
        │  _build_patient_profile() → "Age: 12. Location: New York. Treatments tried: ..."
        │  log_session() → Supabase
        │  run_faro(condition, patient_profile)
        │
        ▼ crew.py → create_agents() + create_tasks()
        │
        │  ┌─────────────────────── PARALLEL ────────────────────────┐
        │  │                                                          │
        │  │  Thread A                          Thread B              │
        │  │  Trial Scout                       Literature Agent      │
        │  │  → ClinicalTrialsTool._run()       → PubMedTool._run()   │
        │  │    tools.search_clinical_trials()    tools.search_pubmed()│
        │  │    GET clinicaltrials.gov/api/v2     GET eutils esearch   │
        │  │    → 5 trials (JSON)                 GET eutils efetch    │
        │  │  → ISRCTNTool._run()                 → 5 papers (XML)    │
        │  │    tools.search_isrctn()                                 │
        │  │    GET isrctn.com/api/query           ← lit_result str   │
        │  │    relevance filter                                       │
        │  │  ← trials_result str                                     │
        │  └──────────────────────────────────────────────────────────┘
        │
        │  combined_context = f"TRIALS FOUND:\n{trials_result}\n\nLITERATURE:\n{lit_result}"
        │
        │  ┌───────────────────── SEQUENTIAL ─────────────────────────┐
        │  │                                                           │
        │  │  Eligibility Assessor                                     │
        │  │  reads combined_context from task description             │
        │  │  → per-trial ratings: Likely / Possibly / Ineligible      │
        │  │                                                           │
        │  │  Patient Navigator (Synthesizer)                          │
        │  │  reads eligibility output via CrewAI context chaining     │
        │  │  → 8-section markdown report                              │
        │  └───────────────────────────────────────────────────────────┘
        │
        ▼ crew.py returns str report
        │
        ▼ app.py
        │  inject date + disclaimer blockquote
        │  update_session_report_generated() → Supabase
        │  st.markdown(report)
        │  Download button → log_download() → Supabase
```

---

*Built by Pooja Kotecha · [dinq.me/pkotecha-eng](https://dinq.me/pkotecha-eng)*
