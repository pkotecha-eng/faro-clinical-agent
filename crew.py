"""
FARO Clinical Agent - Crew Orchestration
Parallel execution where possible
"""

from crewai import Crew, Process
from agents import create_agents
from tasks import create_tasks
import os
from dotenv import load_dotenv
load_dotenv()

os.environ["OPENAI_API_KEY"] = "NA"  # dummy to satisfy checks
os.environ["ANTHROPIC_API_KEY"] = os.getenv("ANTHROPIC_API_KEY")


def run_faro(condition: str, patient_profile: str) -> str:
    """
    Run the FARO multi-agent crew.
    
    Trial Scout and Literature Agent run in parallel.
    Eligibility Assessor runs after Trial Scout.
    Synthesizer runs last with all context.
    """

    # Create agents
    agents = create_agents()
    trial_scout, literature_agent, eligibility_assessor, synthesizer = agents

    # Create tasks
    find_trials, search_literature, assess_eligibility, synthesize_report = create_tasks(
        agents=agents,
        condition=condition,
        patient_profile=patient_profile,
    )

    # Build crew with parallel execution
    crew = Crew(
        agents=[trial_scout, literature_agent, eligibility_assessor, synthesizer],
        tasks=[find_trials, search_literature, assess_eligibility, synthesize_report],
        process=Process.sequential,  # CrewAI handles parallel via task context
        verbose=True,
    )

    result = crew.kickoff()
    return str(result)


if __name__ == "__main__":
    # Quick test
    result = run_faro(
        condition="pediatric epilepsy",
        patient_profile="8 year old child, diagnosed with focal epilepsy, "
                       "failed two medications (levetiracetam and valproate), "
                       "located in New York",
    )
    print(result)