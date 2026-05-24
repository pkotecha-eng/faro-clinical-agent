"""
FARO Clinical Agent - Agent Definitions
Four specialized agents working in parallel where possible
"""

from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from tools import search_pubmed, search_clinical_trials, search_isrctn
import os
from dotenv import load_dotenv
from crewai import Agent, LLM

load_dotenv()

haiku = LLM(
    model="claude-haiku-4-5-20251001",
    api_key=os.environ.get("ANTHROPIC_API_KEY"),
)

claude = LLM(
    model="claude-sonnet-4-5",
    api_key=os.environ.get("ANTHROPIC_API_KEY"),
)


class PubMedInput(BaseModel):
    query: str = Field(..., description="Search query for PubMed")


class TrialsInput(BaseModel):
    condition: str = Field(..., description="Medical condition to search trials for")


class PubMedTool(BaseTool):
    name: str = "Search PubMed"
    description: str = "Search PubMed for peer-reviewed biomedical literature on a condition or treatment."
    args_schema: type[BaseModel] = PubMedInput

    def _run(self, query: str) -> str:
        results = search_pubmed(query=query, max_results=5)
        if not results:
            return "No papers found."
        output = []
        for p in results:
            output.append(
                f"Title: {p.get('title')}\n"
                f"Authors: {', '.join(p.get('authors', []))}\n"
                f"Journal: {p.get('journal')} ({p.get('year')})\n"
                f"Abstract: {p.get('abstract', '')[:500]}\n"
                f"URL: {p.get('url')}\n"
            )
        return "\n---\n".join(output)


class ClinicalTrialsTool(BaseTool):
    name: str = "Search Clinical Trials"
    description: str = "Search ClinicalTrials.gov for recruiting trials for a given condition."
    args_schema: type[BaseModel] = TrialsInput

    def _run(self, condition: str) -> str:
        results = search_clinical_trials(condition=condition, status="RECRUITING", max_results=5)
        if not results:
            return "No trials found."
        output = []
        for t in results:
            output.append(
                f"Title: {t.get('title')}\n"
                f"NCT ID: {t.get('nct_id')}\n"
                f"Phase: {t.get('phase')}\n"
                f"Sponsor: {t.get('sponsor')}\n"
                f"Primary Outcome: {t.get('primary_outcome', '')}\n"
                f"Status: {t.get('status')}\n"
                f"Eligibility: {t.get('eligibility_criteria', '')[:600]}\n"
                f"Locations: {', '.join(t.get('locations', []))}\n"
                f"URL: {t.get('url')}\n"
            )
        return "\n---\n".join(output)


pubmed_tool = PubMedTool()
trials_tool = ClinicalTrialsTool()


class ISRCTNInput(BaseModel):
    query: str = Field(..., description="Condition or search terms for ISRCTN registry")


class ISRCTNTool(BaseTool):
    name: str = "Search ISRCTN"
    description: str = "Search ISRCTN registry for UK and European clinical trials not listed on ClinicalTrials.gov."
    args_schema: type[BaseModel] = ISRCTNInput

    def _run(self, query: str) -> str:
        results = search_isrctn(query=query, max_results=5)
        if not results:
            return "No ISRCTN trials found."
        output = []
        for t in results:
            output.append(
                f"Title: {t.get('title')}\n"
                f"ISRCTN ID: {t.get('trial_id')}\n"
                f"Phase: {t.get('phase')}\n"
                f"Sponsor: {t.get('sponsor')}\n"
                f"Status: {t.get('status')}\n"
                f"Countries: {', '.join(t.get('countries', []))}\n"
                f"Primary Outcome: {t.get('primary_outcome', '')}\n"
                f"Eligibility: {t.get('eligibility_criteria', '')[:600]}\n"
                f"URL: {t.get('url')}\n"
            )
        return "\n---\n".join(output)


isrctn_tool = ISRCTNTool()

def create_agents():
    """Create and return all FARO agents."""

    trial_scout = Agent(
        role="Clinical Trial Scout",
        goal="Find the most relevant recruiting clinical trials for the patient's condition",
        backstory=(
            "You are an expert clinical trial coordinator with 10 years of experience "
            "searching ClinicalTrials.gov. You know how to find trials that match patient "
            "profiles and understand inclusion/exclusion criteria deeply."
        ),
        tools=[trials_tool, isrctn_tool],
        llm=haiku,
        verbose=True,
        allow_delegation=False,
    )

    literature_agent = Agent(
        role="Medical Literature Researcher",
        goal="Find and summarize the latest published evidence for the patient's condition",
        backstory=(
            "You are a biomedical researcher who specializes in synthesizing peer-reviewed "
            "literature from PubMed. You find the most relevant and recent studies and "
            "explain them in plain language that patients and caregivers can understand."
        ),
        tools=[pubmed_tool],
        llm=haiku,
        verbose=True,
        allow_delegation=False,
    )

    eligibility_assessor = Agent(
        role="Trial Eligibility Specialist",
        goal="Assess whether the patient likely qualifies for each trial found",
        backstory=(
            "You are a clinical trial eligibility specialist who has reviewed thousands "
            "of patient profiles against trial criteria. You carefully read inclusion and "
            "exclusion criteria and provide honest, plain-language assessments of fit. "
            "You always note that final eligibility must be confirmed with the trial site."
        ),
        tools=[],
        verbose=True,
        llm=claude,
        allow_delegation=False,
    )

    synthesizer = Agent(
        role="Patient Care Navigator",
        goal="Create a clear, compassionate, actionable report for the patient and their doctor",
        backstory=(
            "You are a patient navigator who bridges the gap between complex medical "
            "research and patients seeking help. You synthesize findings from multiple "
            "sources into a clear, organized report that a patient can bring to their "
            "doctor. You write with empathy, clarity, and hope."
        ),
        tools=[],
        llm=claude,
        verbose=True,
        allow_delegation=False,
    )

    return trial_scout, literature_agent, eligibility_assessor, synthesizer