# 🔦 FARO — Clinical Trial Intelligence for Patients

FARO is a multi-agent AI system that helps patients and caregivers find and understand clinical trials. Enter a diagnosis, age, location, and treatment history — four specialized AI agents search live medical databases and generate a personalized report you can bring to your doctor.

## What it does

FARO uses four specialized CrewAI agents working in sequence:

1. **🔍 Trial Scout** — searches ClinicalTrials.gov for recruiting trials matching the condition
2. **📚 Literature Researcher** — searches PubMed for the latest peer-reviewed evidence
3. **✅ Eligibility Specialist** — assesses whether the patient likely qualifies for each trial
4. **🧭 Patient Navigator** — synthesizes everything into a plain-language report

## What the report includes

- Patient summary in plain language
- Latest research findings from PubMed
- Matched trials ranked by eligibility fit with NCT IDs and links
- Per-trial eligibility assessment with reasoning
- Questions to ask your doctor
- Concrete next steps
- Important disclaimer

## Tech stack

- Claude (claude-sonnet-4-5) via Anthropic API
- CrewAI 1.14.2 — role-based multi-agent orchestration
- PubMed API (NCBI E-utilities) — no key required
- ClinicalTrials.gov API v2 — no key required
- Python + Streamlit

## Setup

```bash
git clone https://github.com/pkotecha-eng/faro-clinical-agent
cd faro-clinical-agent
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Add your Anthropic API key to `.env`:
ANTHROPIC_API_KEY=your_key_here

Run:
```bash
streamlit run app.py
```

## Note

For informational purposes only. Always consult your healthcare team before making any medical decisions. Trial eligibility must be confirmed with the trial site.

## Built by

Pooja Kotecha · [dinq.me/pkotecha-eng](https://dinq.me/pkotecha-eng)