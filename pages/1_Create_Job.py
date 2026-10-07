import streamlit as st

from db import create_job
from parser import extract_text


# ============================================================
# PAGE TITLE
# ============================================================

st.title("Create Job")

st.caption(
    "Create a job before processing candidate resumes."
)

st.divider()


# ============================================================
# JOB CREATION FORM
# ============================================================

with st.container(border=True):
    job_title = st.text_input(
        "Job Title",
        placeholder="Example: Junior Data Analyst"
    )

    seniority_level = st.selectbox(
        "Job Level",
        [
            "Internship",
            "Entry Level",
            "Junior",
            "Mid Level",
            "Senior",
            "Lead / Manager",
        ]
    )

    st.subheader("Job Description")
    description_source = st.radio(
        "How would you like to provide the job description?",
        ["Upload File", "Paste Text"],
        horizontal=True,
        key="job_description_source"
    )

    uploaded_jd = None
    pasted_description = ""

    if description_source == "Upload File":
        uploaded_jd = st.file_uploader(
            "Upload Job Description",
            type=["pdf", "docx", "txt"],
            accept_multiple_files=False
        )
    else:
        pasted_description = st.text_area(
            "Paste the complete job description",
            height=300,
            placeholder=(
                "Example:\n\n"
                "We are looking for a Junior Data Analyst.\n\n"
                "Requirements:\n"
                "- Bachelor's degree in Computer Science, "
                "Information Systems, Data Science or related field.\n"
                "- Knowledge of Python and SQL.\n"
                "- Strong analytical skills.\n"
                "- Knowledge of data visualization.\n\n"
                "Preferred:\n"
                "- Experience with Power BI.\n"
                "- Internship experience is an advantage."
            )
        )

    submit = st.button(
        "Create Job",
        type="primary"
    )


# ============================================================
# PROCESS FORM SUBMISSION
# ============================================================

if submit:

    # ========================================================
    # VALIDATE JOB TITLE
    # ========================================================

    if not job_title.strip():

        st.error(
            "Please enter a job title."
        )

        st.stop()


    # ========================================================
    # VARIABLES
    # ========================================================

    description = ""

    source_filename = None


    # ========================================================
    # UPLOAD FILE MODE
    # ========================================================

    if description_source == "Upload File":

        # ----------------------------------------------------
        # Check file
        # ----------------------------------------------------

        if uploaded_jd is None:

            st.error(
                "Please upload a job description."
            )

            st.stop()


        # ----------------------------------------------------
        # Read uploaded file
        # ----------------------------------------------------

        file_bytes = uploaded_jd.getvalue()


        # ----------------------------------------------------
        # Extract text
        # ----------------------------------------------------

        (
            description,
            extraction_status
        ) = extract_text(
            file_bytes,
            uploaded_jd.name
        )


        # ----------------------------------------------------
        # Save original filename
        # ----------------------------------------------------

        source_filename = uploaded_jd.name


        # ----------------------------------------------------
        # Low text warning
        # ----------------------------------------------------

        if extraction_status == "LOW_TEXT_WARNING":

            st.warning(
                "The file contains very little selectable "
                "text. It may be a scanned document and may "
                "require OCR in a later version."
            )


        # ----------------------------------------------------
        # Extraction error
        # ----------------------------------------------------

        elif extraction_status != "SUCCESS":

            st.error(
                "Could not read the job description: "
                f"{extraction_status}"
            )

            st.stop()


    # ========================================================
    # PASTE TEXT MODE
    # ========================================================

    else:

        description = (
            pasted_description.strip()
        )


        # ----------------------------------------------------
        # Check pasted text
        # ----------------------------------------------------

        if not description:

            st.error(
                "Please paste the job description."
            )

            st.stop()


        # ----------------------------------------------------
        # Mark as text input
        # ----------------------------------------------------

        source_filename = None


    # ========================================================
    # SAVE JOB
    # ========================================================

    job_id = create_job(

        job_title=job_title,

        seniority_level=seniority_level,

        description=description,

        source_filename=source_filename,
    )


    # ========================================================
    # SUCCESS MESSAGE
    # ========================================================

    st.success(
        f"Job created successfully. "
        f"Job ID: {job_id}"
    )


    st.info(
        "The job has been saved as DRAFT. "
        "The next stage will analyze the job description "
        "and extract its requirements."
    )


    # ========================================================
    # SHOW SAVED DESCRIPTION
    # ========================================================

    with st.expander(
        "View saved job description"
    ):

        st.text_area(

            "Job Description",

            description,

            height=400,

            disabled=True,

            key=f"saved_description_{job_id}"
        )