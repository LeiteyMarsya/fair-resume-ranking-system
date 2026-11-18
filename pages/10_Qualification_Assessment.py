
import streamlit as st
import db
import re


# ---------------------------------------------------------
# PAGE SETUP
# ---------------------------------------------------------

st.title("Qualification Assessment")
st.caption(
    "Independently assess candidate qualifications "
    "using recruiter-confirmed job requirements."
)

db.init_database()


# ---------------------------------------------------------
# RESUME ANONYMIZATION
# ---------------------------------------------------------

def anonymize_resume(text, candidate_name=None,
                    candidate_email=None, candidate_phone=None):

    if not text:
        return ""

    # Redact the candidate's stored full name.
    if candidate_name:
        name_pattern = re.escape(candidate_name.strip())
        name_pattern = name_pattern.replace(r"\ ", r"\s+")

        text = re.sub(
            name_pattern,
            "[REDACTED NAME]",
            text,
            flags=re.IGNORECASE
        )

    # Redact the candidate's stored email.
    if candidate_email:
        text = re.sub(
            re.escape(candidate_email.strip()),
            "[REDACTED EMAIL]",
            text,
            flags=re.IGNORECASE
        )

    # Redact email addresses generally.
    text = re.sub(
        r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",
        "[REDACTED EMAIL]",
        text
    )

    # Redact detected phone-number patterns.
    text = re.sub(
        r"(?<!\w)\+?\d[\d\s().-]{6,}\d(?!\w)",
        "[REDACTED PHONE]",
        text
    )

    # Redact URLs that may identify the candidate.
    text = re.sub(
        r"(https?://\S+|www\.\S+)",
        "[REDACTED URL]",
        text,
        flags=re.IGNORECASE
    )

    return text


# ---------------------------------------------------------
# LOAD APPLICATIONS AND CHECK ELIGIBILITY
# ---------------------------------------------------------

all_applications = db.get_application_assessment_details()

eligible_applications = []
requirements_cache = {}

for application in all_applications:

    job_id = application["job_id"]

    # Only load requirements once for each job.
    if job_id not in requirements_cache:
        requirements_cache[job_id] = db.get_job_requirements(job_id)

    requirements = requirements_cache[job_id]

    # A job must be active and confirmed.
    if application["job_status"] != "ACTIVE":
        continue

    if application["requirements_confirmed"] != 1:
        continue

    # At least one requirement must exist.
    if not requirements:
        continue

    # Every requirement must be recruiter-verified.
    if not all(
        requirement["recruiter_verified"] == 1
        for requirement in requirements
    ):
        continue

    eligible_applications.append(application)


# ---------------------------------------------------------
# LOAD EXISTING REAL QUALIFICATION LABELS
# ---------------------------------------------------------

existing_labels = db.get_qualification_labels(
    include_simulated=False
)

labels_by_application = {
    label["application_id"]: label
    for label in existing_labels
}


# ---------------------------------------------------------
# APPLICATION SELECTION
# ---------------------------------------------------------

st.header("1. Select Application")

if not eligible_applications:

    st.warning(
        "No eligible applications are available. "
        "Make sure the job is ACTIVE and all requirements "
        "have been recruiter-confirmed."
    )

    st.stop()


application_lookup = {
    application["application_id"]: application
    for application in eligible_applications
}

application_ids = list(application_lookup.keys())

selected_application_id = st.selectbox(
    "Choose a candidate application",
    options=application_ids,
    format_func=lambda app_id: (
        f"{application_lookup[app_id]['blind_id']} "
        f"| Application #{app_id} "
        f"| {application_lookup[app_id]['job_title']}"
    )
)

application = application_lookup[selected_application_id]


# ---------------------------------------------------------
# JOB INFORMATION
# ---------------------------------------------------------

st.divider()

st.header("2. Job Information")

st.write("**Job Title:**", application["job_title"])

st.write(
    "**Seniority Level:**",
    application["seniority_level"] or "Not specified"
)

st.write("**Job Description:**")

st.write(
    application["job_description"]
    or "No job description available."
)


# ---------------------------------------------------------
# RECRUITER-CONFIRMED REQUIREMENTS
# ---------------------------------------------------------

st.subheader("Recruiter-Confirmed Requirements")

requirements = requirements_cache[application["job_id"]]

for index, requirement in enumerate(requirements, start=1):

    requirement_text = requirement["requirement_text"]

    category = requirement["category"] or "Unspecified"
    requirement_type = requirement["requirement_type"] or "Unspecified"

    mandatory_status = (
        "Mandatory"
        if requirement["mandatory"] == 1
        else "Preferred / Not marked mandatory"
    )

    st.markdown(
        f"**{index}. {requirement_text}**  \n"
        f"Category: {category} | "
        f"Type: {requirement_type} | "
        f"{mandatory_status}"
    )


# ---------------------------------------------------------
# RESUME REVIEW
# ---------------------------------------------------------

st.divider()

st.header("3. Review Candidate Resume")

st.write(
    "**Candidate Blind ID:**",
    application["blind_id"]
)

st.write(
    "**Resume Extraction Status:**",
    application["extraction_status"]
)

resume_text = application["extracted_text"] or ""

if not resume_text.strip():

    st.error(
        "Resume text is unavailable. "
        "This application cannot be assessed."
    )

    st.stop()


anonymized_resume = anonymize_resume(
    text=resume_text,
    candidate_name=application["candidate_name"],
    candidate_email=application["candidate_email"],
    candidate_phone=application["candidate_phone"]
)

st.info(
    "Personal information is masked where detected. "
    "Please do not use identifying information when "
    "making your qualification decision."
)

with st.expander("View Anonymized Resume", expanded=True):

    st.text_area(
        "Resume Content",
        value=anonymized_resume,
        height=400,
        disabled=True
    )


# ---------------------------------------------------------
# INDEPENDENT QUALIFICATION DECISION
# ---------------------------------------------------------

st.divider()

st.header("4. Independent Qualification Decision")

st.write(
    "Assess the candidate based on the resume and "
    "recruiter-confirmed requirements above."
)

st.warning(
    "Do not use previous screening scores, ranking results "
    "or selection decisions when making this assessment."
)

existing_label = labels_by_application.get(
    selected_application_id
)

if existing_label is None:

    default_decision = None

else:

    default_decision = (
        "Qualified"
        if existing_label["is_qualified"] == 1
        else "Not Qualified"
    )

decision = st.radio(
    "Qualification Result",
    options=["Qualified", "Not Qualified"],
    index=None if default_decision is None else (
        0 if default_decision == "Qualified" else 1
    ),
    horizontal=True
)


# ---------------------------------------------------------
# EXISTING ASSESSMENT INFORMATION
# ---------------------------------------------------------

if existing_label is not None:

    st.info(
        "An independent qualification assessment already "
        "exists for this application. Saving a new decision "
        "will update the existing assessment."
    )

    st.caption(
        f"Previous assessment recorded at: "
        f"{existing_label['recorded_at']}"
    )


# ---------------------------------------------------------
# SAVE ASSESSMENT
# ---------------------------------------------------------

if st.button(
    "Save Qualification Assessment",
    type="primary"
):

    if decision is None:

        st.error("Please select Qualified or Not Qualified.")

    else:

        is_qualified = decision == "Qualified"

        try:

            db.save_qualification_label(
                application_id=selected_application_id,
                is_qualified=is_qualified,
                is_simulated=False,
                qualification_source="INDEPENDENT_HUMAN_ASSESSMENT"
            )

            st.success(
                f"Assessment saved successfully: {decision}"
            )

            st.rerun()

        except Exception as error:

            st.error(
                f"Unable to save assessment: {error}"
            )


# ---------------------------------------------------------
# ASSESSMENT GUIDELINES
# ---------------------------------------------------------

st.divider()

st.caption(
    "Assessment guidelines: Use only recruiter-confirmed "
    "requirements and resume qualifications. Demographic "
    "information and previous screening outcomes must not "
    "influence the independent qualification decision."
)
