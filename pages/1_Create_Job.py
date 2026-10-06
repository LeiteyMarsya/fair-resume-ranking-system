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

with st.form(
    "create_job_form"
):

    # --------------------------------------------------------
    # JOB TITLE
    # --------------------------------------------------------

    job_title = st.text_input(
        "Job Title",
        placeholder="Example: Junior Data Analyst"
    )

    # --------------------------------------------------------
    # SENIORITY
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # JOB DESCRIPTION SOURCE
    # --------------------------------------------------------

    st.subheader(
        "Job Description"
    )

    description_source = st.radio(
        "How would you like to provide the job description?",
        [
            "Upload File",
            "Paste Text"
        ],
        horizontal=True
    )

    uploaded_jd = None
    pasted_description = ""

    # --------------------------------------------------------
    # UPLOAD FILE
    # --------------------------------------------------------

    if description_source == "Upload File":

        uploaded_jd = st.file_uploader(
            "Upload Job Description",
            type=[
                "pdf",
                "docx",
                "txt"
            ],
            accept_multiple_files=False
        )

    # --------------------------------------------------------
    # PASTE TEXT
    # --------------------------------------------------------

    else:

        pasted_description = st.text_area(
            "Paste the complete job description",
            height=300,
            placeholder=(
                "Paste the complete job description here..."
            )
        )

    # --------------------------------------------------------
    # SUBMIT
    # --------------------------------------------------------

    submit = st.form_submit_button(
        "Create Job",
        type="primary"
    )


# ============================================================
# PROCESS SUBMISSION
# ============================================================

if submit:

    # --------------------------------------------------------
    # VALIDATE JOB TITLE
    # --------------------------------------------------------

    if not job_title.strip():

        st.error(
            "Please enter a job title."
        )

        st.stop()

    # --------------------------------------------------------
    # INITIALIZE VARIABLES
    # --------------------------------------------------------

    description = ""
    source_filename = None

    # ========================================================
    # FILE INPUT
    # ========================================================

    if description_source == "Upload File":

        if uploaded_jd is None:

            st.error(
                "Please upload a job description."
            )

            st.stop()

        # Read uploaded file
        file_bytes = uploaded_jd.getvalue()

        # Extract text
        description, extraction_status = extract_text(
            file_bytes,
            uploaded_jd.name
        )

        source_filename = uploaded_jd.name

        # ----------------------------------------------------
        # LOW TEXT WARNING
        # ----------------------------------------------------

        if extraction_status == "LOW_TEXT_WARNING":

            st.warning(
                "The file contains very little selectable text. "
                "It may be a scanned document and may require OCR "
                "in a later version."
            )

        # ----------------------------------------------------
        # EXTRACTION ERROR
        # ----------------------------------------------------

        elif extraction_status != "SUCCESS":

            st.error(
                "Could not read the job description: "
                f"{extraction_status}"
            )

            st.stop()

    # ========================================================
    # TEXT INPUT
    # ========================================================

    else:

        description = (
            pasted_description
            .strip()
        )

        if not description:

            st.error(
                "Please paste the job description."
            )

            st.stop()


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
    # SUCCESS
    # ========================================================

    st.success(
        f"Job created successfully. Job ID: {job_id}"
    )

    st.info(
        "The job has been saved as DRAFT. "
        "The next stage will analyze the job description "
        "and extract its requirements."
    )


    # ========================================================
    # SHOW EXTRACTED TEXT
    # ========================================================

    with st.expander(
        "View extracted job description"
    ):

        st.text_area(
            "Extracted Text",
            description,
            height=400,
            disabled=True
        )