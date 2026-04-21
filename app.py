"""
FARO — Clinical Trial Intelligence for Patients
Patient-facing Streamlit web app
"""

import streamlit as st
from crew import run_faro
from datetime import date

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

        st.divider()
        st.markdown("### 🤖 FARO is working...")
        st.caption("Four AI agents are searching trials, reviewing research, and preparing your report. This takes 2-3 minutes.")

        progress_placeholder = st.empty()
        progress_placeholder.info("🔍 Trial Scout searching ClinicalTrials.gov...")

        with st.spinner("Generating your personalized report..."):
            try:
                result = run_faro(
                    condition=condition,
                    patient_profile=patient_profile,
                )

                # Inject date as subheading under the report title
                lines = result.split('\n')
                for i, line in enumerate(lines):
                    if line.startswith('# '):
                        lines.insert(i + 1, f"### {date.today().strftime('%B %d, %Y')}")
                        break
                result = '\n'.join(lines)

                progress_placeholder.empty()

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

            except Exception as e:
                progress_placeholder.empty()
                st.error(f"Something went wrong: {e}. Please try again.")