"""
FARO Clinical Agent - Crew Orchestration
Parallel execution where possible
"""

from crewai import Crew, Process
from agents import create_agents
from tasks import create_tasks
from concurrent.futures import ThreadPoolExecutor
import os
from dotenv import load_dotenv
load_dotenv(override=True)

os.environ["OPENAI_API_KEY"] = "NA"  # dummy to satisfy checks
os.environ["ANTHROPIC_API_KEY"] = os.getenv("ANTHROPIC_API_KEY")


def run_faro(condition: str, patient_profile: str) -> str:
    agents = create_agents()
    trial_scout, literature_agent, eligibility_assessor, synthesizer = agents

    find_trials, search_literature, assess_eligibility, synthesize_report = create_tasks(
        agents=agents,
        condition=condition,
        patient_profile=patient_profile,
    )

    # Run Trial Scout and Literature Researcher in parallel
    def run_task(task, agent):
        crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=True)
        return str(crew.kickoff())

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_trials = executor.submit(run_task, find_trials, trial_scout)
        future_lit = executor.submit(run_task, search_literature, literature_agent)
        trials_result = future_trials.result()
        lit_result = future_lit.result()

    # Run Eligibility Assessor then Synthesizer sequentially with combined context
    combined_context = f"TRIALS FOUND:\n{trials_result}\n\nLITERATURE:\n{lit_result}"

    _, _, assess_eligibility_task, synthesize_report_task = create_tasks(
        agents=agents,
        condition=condition,
        patient_profile=patient_profile,
        context=combined_context,
    )

    crew = Crew(
        agents=[eligibility_assessor, synthesizer],
        tasks=[assess_eligibility_task, synthesize_report_task],
        process=Process.sequential,
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