"""
FARO Eval — Integration Tests
Runs each test case through run_faro() and checks output quality.
Results written to eval/results.json
"""

import json
import sys
import os
from datetime import datetime

# Add project root to path so we can import run_faro
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crew import run_faro

EXPECTED_SECTIONS = [
    "0. WHAT THIS MEANS FOR YOU",
    "1. PATIENT SUMMARY",
    "2. WHAT THE RESEARCH SAYS",
    "3. CLINICAL TRIALS MATCHED",
    "4. ELIGIBILITY ASSESSMENT",
    "5. QUESTIONS TO ASK YOUR DOCTOR",
    "6. NEXT STEPS",
    "7. IMPORTANT DISCLAIMER",
]

TRIAL_INDICATORS = ["NCT", "ISRCTN", "clinicaltrials.gov", "Phase", "Recruiting"]


def check_sections(report: str) -> dict:
    results = {}
    for section in EXPECTED_SECTIONS:
        results[section] = section in report
    return results


def check_trial_found(report: str) -> bool:
    return any(indicator in report for indicator in TRIAL_INDICATORS)


def check_min_length(report: str, min_chars: int = 1000) -> bool:
    return len(report) >= min_chars


def run_single(tc: dict) -> dict:
    condition = tc["condition"]
    parts = []
    if tc.get("age"):
        parts.append(f"Age: {tc['age']}")
    if tc.get("location"):
        parts.append(f"Location: {tc['location']}")
    if tc.get("treatments_tried"):
        parts.append(f"Treatments tried: {tc['treatments_tried']}")
    if tc.get("other_info"):
        parts.append(f"Additional information: {tc['other_info']}")
    patient_profile = ". ".join(parts) if parts else "No additional profile information provided."

    result = {
        "id": tc["id"],
        "condition": condition,
        "age": tc.get("age"),
        "timestamp": datetime.utcnow().isoformat(),
        "completed": False,
        "error": None,
        "checks": {
            "trial_found": False,
            "min_length": False,
            "sections": {}
        },
        "passed": False,
        "report": None,
    }

    try:
        report = run_faro(condition=condition, patient_profile=patient_profile)
        result["completed"] = True
        result["report"] = report
        result["checks"]["trial_found"] = check_trial_found(report)
        result["checks"]["min_length"] = check_min_length(report)
        result["checks"]["sections"] = check_sections(report)

        all_sections_present = all(result["checks"]["sections"].values())
        result["passed"] = (
            result["completed"]
            and result["checks"]["trial_found"]
            and result["checks"]["min_length"]
            and all_sections_present
        )

    except Exception as e:
        result["error"] = str(e)

    return result


def main():
    # Load test cases
    cases_path = os.path.join(os.path.dirname(__file__), "test_cases.json")
    with open(cases_path) as f:
        test_cases = json.load(f)
    
        #test_cases = [tc for tc in test_cases if tc["id"] in ("tc_004")]


    print(f"Running {len(test_cases)} test cases...\n")

    results = []
    for tc in test_cases:
        print(f"  Running {tc['id']} — {tc['condition']} ({tc.get('age', 'no age')})...")
        result = run_single(tc)
        status = "✅ PASS" if result["passed"] else "❌ FAIL"
        print(f"  {status}\n")
        results.append(result)

    # Summary
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    print(f"Results: {passed}/{total} passed\n")

    # Write results.json
    output = {
        "run_at": datetime.utcnow().isoformat(),
        "summary": {"passed": passed, "total": total},
        "results": results,
    }
    results_path = os.path.join(os.path.dirname(__file__), "results.json")
    with open(results_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Results written to eval/results.json")


if __name__ == "__main__":
    main()