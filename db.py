"""
FARO - Supabase database client
Handles session logging and eval tracking
"""

import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

def get_client() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")
    return create_client(url, key)

def get_service_client() -> Client:
    """Service role client — bypasses RLS. Use only for server-side updates."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    return create_client(url, key)

def log_session(session_id: str, condition: str, patient_profile: str, patient_type: str = "unknown") -> dict:
    """Log a new FARO session."""
    try:
        client = get_client()
        result = client.table("faro_sessions").insert({
            "session_id": session_id,
            "condition": condition,
            "patient_profile": patient_profile,
            "patient_type": patient_type,
            "report_generated": False,
            "report_downloaded": False
        }).execute()
        return result.data[0] if result.data else {}
    except Exception as e:
        print(f"Session logging error: {e}")
        return {}

def update_session_report_generated(session_id: str) -> None:
    """Mark report as generated for a session."""
    try:
        client = get_service_client()
        client.table("faro_sessions").update({
            "report_generated": True
        }).eq("session_id", session_id).execute()
    except Exception as e:
        print(f"Session update error: {e}")

def update_session_downloaded(session_id: str) -> None:
    """Mark report as downloaded for a session."""
    try:
        client = get_service_client()
        client.table("faro_sessions").update({
            "report_downloaded": True
        }).eq("session_id", session_id).execute()
    except Exception as e:
        print(f"Download update error: {e}")

def get_past_searches(condition: str, limit: int = 5) -> list:
    """Retrieve past searches for the same condition — memory layer."""
    try:
        client = get_client()
        result = client.table("faro_sessions").select(
            "condition, patient_profile, created_at"
        ).ilike("condition", f"%{condition}%").eq(
            "report_generated", True
        ).order("created_at", desc=True).limit(limit).execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"Memory retrieval error: {e}")
        return []

def log_eval_run(condition: str, faro_version: str, scores: dict) -> None:
    """Log an eval run result."""
    try:
        client = get_client()
        client.table("faro_eval_runs").insert({
            "condition": condition,
            "faro_version": faro_version,
            "retrieval_precision": scores.get("retrieval_precision"),
            "sections_complete": scores.get("sections_complete"),
            "section_0_jargon_free": scores.get("section_0_jargon_free"),
            "trial_ids_found": scores.get("trial_ids_found", []),
            "report_word_count": scores.get("report_word_count")
        }).execute()
    except Exception as e:
        print(f"Eval logging error: {e}")

def update_session_feedback(session_id: str, feedback: str) -> None:
    """Record user feedback (positive/negative) for a session."""
    try:
        client = get_service_client()
        client.table("faro_sessions").update({
            "feedback": feedback
        }).eq("session_id", session_id).execute()
    except Exception as e:
        print(f"Feedback update error: {e}")