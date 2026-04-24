"""
FARO Clinical Agent - Task Definitions
Tasks assigned to each agent
"""

from crewai import Task
from datetime import date


def create_tasks(agents, condition: str, patient_profile: str, context: str = None):
    """Create and return all FARO tasks."""

    trial_scout, literature_agent, eligibility_assessor, synthesizer = agents

    # Task 1 — runs in parallel with Task 2
    find_trials = Task(
        description=(
            f"Search ClinicalTrials.gov for recruiting clinical trials for: {condition}.\n"
            f"Find up to 5 relevant recruiting trials. For each trial capture:\n"
            f"- NCT ID, title, phase, sponsor\n"
            f"- Full eligibility criteria (inclusion and exclusion)\n"
            f"- Locations\n"
            f"- URL\n"
            f"Return all trials with complete details."
        ),
        expected_output=(
            "A detailed list of up to 5 recruiting clinical trials with NCT IDs, "
            "phases, sponsors, eligibility criteria, locations, and URLs."
        ),
        agent=trial_scout,
    )

    # Task 2 — runs in parallel with Task 1
    search_literature = Task(
        description=(
            f"Search PubMed for the latest peer-reviewed evidence on: {condition}.\n"
            f"Find up to 5 relevant papers. For each paper capture:\n"
            f"- Title, authors, journal, year\n"
            f"- Key findings from the abstract\n"
            f"- URL\n"
            f"Focus on recent studies (last 3 years if possible), "
            f"treatment options, and promising interventions."
        ),
        expected_output=(
            "A summary of up to 5 peer-reviewed papers with titles, authors, "
            "journals, years, key findings, and PubMed URLs."
        ),
        agent=literature_agent,
    )

    # Task 3 — uses injected context string if provided (parallel flow),
    # otherwise uses CrewAI task reference (sequential flow)
    context_text = context if context else "See trial search results above."

    assess_eligibility = Task(
        description=(
            f"Based on the clinical trials found, assess eligibility for this patient:\n\n"
            f"Patient Profile: {patient_profile}\n\n"
            f"Trial and literature context:\n{context_text}\n\n"
            f"For each trial:\n"
            f"1. State the NCT ID and trial title\n"
            f"2. List key inclusion criteria and whether this patient likely meets them\n"
            f"3. List key exclusion criteria and flag any potential disqualifiers\n"
            f"4. Rate eligibility: Likely Eligible / Possibly Eligible / Likely Ineligible\n"
            f"5. Explain your reasoning in plain language\n\n"
            f"Always note that final eligibility must be confirmed with the trial site."
        ),
        expected_output=(
            "An eligibility assessment for each trial with ratings "
            "(Likely Eligible / Possibly Eligible / Likely Ineligible) "
            "and plain-language reasoning."
        ),
        agent=eligibility_assessor,
        context=[] if context else [find_trials],
    )

    # Task 4 — runs last, synthesizes everything
    synthesize_report = Task(
        description=(
            f"Today's date is {date.today().strftime('%B %d, %Y')}. Use this as the report date.\n\n"
            f"Create a comprehensive, compassionate patient report combining all findings.\n\n"
            + (f"Context from parallel research:\n{context_text}\n\n" if context else "")
            + f"Structure the report as follows:\n\n"
            f"0. WHAT THIS MEANS FOR YOU\n"
            f"   3-4 sentences in plain everyday English summarizing the most important findings. "
            f"   Write this for a parent or patient with no medical background. "
            f"   No medical terms in this section at all.\n\n"
            f"1. PATIENT SUMMARY\n"
            f"   Brief restatement of the patient's situation\n\n"
            f"2. WHAT THE RESEARCH SAYS\n"
            f"   Plain-language summary of latest evidence from PubMed\n\n"
            f"3. CLINICAL TRIALS MATCHED\n"
            f"   Trials ranked by eligibility fit, with NCT IDs and URLs\n\n"
            f"4. ELIGIBILITY ASSESSMENT\n"
            f"   For each trial — rating and key reasons\n\n"
            f"5. QUESTIONS TO ASK YOUR DOCTOR\n"
            f"   3-5 specific questions based on the findings\n\n"
            f"6. NEXT STEPS\n"
            f"   Concrete actions the patient can take\n\n"
            f"7. IMPORTANT DISCLAIMER\n"
            f"   This is for informational purposes only. "
            f"Always consult your healthcare team before making any decisions.\n\n"
            f"Language rules: Write with empathy, clarity, and hope. "
            f"If a medical term must be used anywhere in the report, define it immediately in plain English in parentheses. "
            f"Section 0 must contain zero medical jargon — no exceptions. "
            f"This report should be something a patient can print and bring to their doctor."
        ),
        expected_output=(
            "A complete, well-structured patient report with all 8 sections, "
            "(sections 0 through 7), written in plain language that a patient "
            "can bring to their doctor."
        ),
        agent=synthesizer,
        context=[] if context else [find_trials, search_literature, assess_eligibility],
    )

    return find_trials, search_literature, assess_eligibility, synthesize_report