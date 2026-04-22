"""
FARO — Clinical Trial Intelligence for Patients
Patient-facing Streamlit web app
"""

import streamlit as st
from crew import run_faro
from datetime import date
import uuid

# ADD SESSION ID SETUP
if 'session_id' not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# ADD LOGGING FUNCTIONS
def log_run(condition, patient_type, session_id):
    with open("faro_runs.log", "a") as f:
        f.write(f"{date.today()},{session_id},{condition},{patient_type}\n")

def log_download(condition, session_id):
    with open("faro_downloads.log", "a") as f:
        f.write(f"{date.today()},{session_id},{condition}\n")


st.html("""
<script defer data-domain="faro-clinical-agent.fly.dev" src="https://plausible.io/js/script.js"></script>
""")

st.set_page_config(
    page_title="FARO — Clinical Trial Intelligence",
    page_icon="🔦",
    layout="wide",
)

def _render_sidebar():
    with st.sidebar:
        st.markdown("### 🔦 FARO")
        st.caption("Clinical Trial Intelligence for Patients")
        st.divider()
        st.markdown("""
**What FARO does:**
- Searches ClinicalTrials.gov for recruiting trials
- Reviews latest PubMed research
- Assesses your eligibility for each trial
- Generates a report to bring to your doctor

**Four AI agents work together:**
1. 🔍 Trial Scout — finds relevant trials
2. 📚 Literature Researcher — reviews evidence
3. ✅ Eligibility Specialist — assesses your fit
4. 🧭 Patient Navigator — writes your report
        """)
        st.divider()
        st.caption("⚠️ For informational purposes only. Always consult your healthcare team.")


def _render_input_form():
    st.markdown("## 🔦 FARO Clinical Trial Intelligence")
    st.caption("Enter your information below. FARO will search for trials and generate a personalized report.")

    with st.form("patient_form"):
        col1, col2 = st.columns(2)

        with col1:
            condition = st.text_input(
                "Medical condition or diagnosis *",
                placeholder="e.g. pediatric epilepsy, lung cancer, Type 2 diabetes",
            )
            age = st.text_input(
                "Age",
                placeholder="e.g. 8 years old, 45 years old",
            )
            location = st.text_input(
                "Location (optional)",
                placeholder="e.g. New York, California",
            )

        with col2:
            treatments_tried = st.text_area(
                "Treatments already tried",
                placeholder="e.g. levetiracetam, valproate — both failed to control seizures",
                height=100,
            )
            other_info = st.text_area(
                "Other relevant medical information",
                placeholder="e.g. genetic test results, other diagnoses, symptoms",
                height=100,
            )
            patient_type = st.radio(
                "Are you searching for a trial for yourself or a family member?",
                ["Real medical situation", "Testing the tool"],
                key="patient_type"
            )

        submitted = st.form_submit_button(
            "🔦 Generate My Report",
            use_container_width=True,
            type="primary",
        )

    return submitted, condition, age, location, treatments_tried, other_info


def _build_patient_profile(age, location, treatments_tried, other_info):
    parts = []
    if age:
        parts.append(f"Age: {age}")
    if location:
        parts.append(f"Location: {location}")
    if treatments_tried:
        parts.append(f"Treatments tried: {treatments_tried}")
    if other_info:
        parts.append(f"Additional information: {other_info}")
    return ". ".join(parts) if parts else "No additional profile information provided."


_render_sidebar()

submitted, condition, age, location, treatments_tried, other_info = _render_input_form()

if submitted:
    if not condition:
        st.error("Please enter a medical condition to search for.")
    else:
        patient_profile = _build_patient_profile(age, location, treatments_tried, other_info)

        log_run(condition, st.session_state.patient_type, st.session_state.session_id)

        st.divider()
        st.markdown("### 🤖 FARO is working...")
        st.caption("Four AI agents are searching trials, reviewing research, and preparing your report. This takes 2-3 minutes.")

        with st.status("Generating your report...", expanded=True) as status:
            try:
                st.write("🔍 Searching trials & research...")
                result = run_faro(
                    condition=condition,
                    patient_profile=patient_profile,
                )

                st.write("✓ Formatting report...")
                # Inject date as subheading under the report title
                lines = result.split('\n')
                for i, line in enumerate(lines):
                    if line.startswith('# '):
                        lines.insert(i + 1, f"### {date.today().strftime('%B %d, %Y')}")
                        # Add disclaimer right after date
                        lines.insert(i + 2, "")
                        lines.insert(i + 3, "> ⚠️ **Educational Information Only** — This report is for informational purposes only and does not constitute medical advice. Always consult your child's healthcare provider before making any treatment decisions. Clinical trial eligibility must be verified directly with trial sites.")
                        break
                result = '\n'.join(lines)

                status.update(label="Report ready!", state="complete")
                st.success("✅ Your report is ready!")
                st.divider()
                st.markdown(result)

                st.divider()
                st.download_button(
                    label="📄 Download Report as Text",
                    data=result,
                    file_name=f"FARO_report_{condition.replace(' ', '_')}.txt",
                    mime="text/plain",
                )

                log_download(condition, st.session_state.session_id)

                # ... feedback buttons ...
                st.divider()
                st.markdown("### Was this report helpful?")
                col1, col2 = st.columns(2)
                with col1:
                     if st.button("👍 Yes, useful"):
                        st.success("Thank you! Your feedback helps improve FARO.")
                with col2:
                     if st.button("👎 Could be better"):
                        st.info("We'd love to know how to improve. Email feedback to pkotecha@gmail.com")
                

            except Exception as e:
                status.update(label="Error occurred", state="error")
                st.error(f"Something went wrong: {e}. Please try again.")