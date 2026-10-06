from __future__ import annotations

from pathlib import Path
import uuid

import streamlit as st

from db import (
    create_application,
    create_candidate,
    create_resume,
    get_all_jobs,
    get_job_applications,
    resume_hash_exists,
)

from parser import (
    PARSER_VERSION,
    calculate_sha256,
    extract_text,
)


# ============================================================
# DIRECTORY CONFIGURATION
# ============================================================

BASE_DIR = Path(
    __file__
).resolve().parents[1]


RESUME_DIR = (
    BASE_DIR
    / "data"
    / "resumes"
)


RESUME_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# PAGE TITLE
# ============================================================

st.title(
    "Upload Resumes"
)

st.caption(
    "Upload multiple candidate resumes for a selected job."
)


# ============================================================
# GET JOBS
# ============================================================

jobs = get_all_jobs()


# ============================================================
# ONLY ACTIVE JOBS
# ============================================================

active_jobs = [
    job
    for job in jobs
    if job["status"] == "ACTIVE"
]


if not active_jobs:

    st.warning(
        "There are no ACTIVE jobs. "
        "Create a job and change its status to ACTIVE "
        "before uploading resumes."
    )

    st.stop()


# ============================================================
# JOB SELECTION
# ============================================================

job_options = {
    (
        f"#{job['job_id']} — "
        f"{job['job_title']}"
    ):
    job["job_id"]

    for job in active_jobs
}


selected_label = st.selectbox(
    "Select Job",
    list(job_options.keys())
)


selected_job_id = job_options[
    selected_label
]


# ============================================================
# FILE UPLOAD
# ============================================================

uploaded_files = st.file_uploader(
    "Upload Candidate Resumes",

    type=[
        "pdf",
        "docx",
        "txt"
    ],

    accept_multiple_files=True,

    help=(
        "You can select multiple resumes at the same time."
    )
)


# ============================================================
# DISPLAY NUMBER OF FILES
# ============================================================

if uploaded_files:

    st.info(
        f"{len(uploaded_files)} resume(s) selected."
    )


# ============================================================
# PROCESS RESUMES
# ============================================================

if uploaded_files:

    if st.button(
        "Process Resumes",
        type="primary"
    ):

        progress = st.progress(0)

        successful = 0
        skipped = 0
        failed = 0

        results = []


        # ====================================================
        # PROCESS EACH FILE
        # ====================================================

        for index, uploaded_file in enumerate(
            uploaded_files
        ):

            filename = uploaded_file.name

            file_bytes = (
                uploaded_file.getvalue()
            )


            try:

                # ============================================
                # FILE HASH
                # ============================================

                file_hash = calculate_sha256(
                    file_bytes
                )


                # ============================================
                # DUPLICATE CHECK
                # ============================================

                if resume_hash_exists(
                    file_hash
                ):

                    skipped += 1

                    results.append(
                        {
                            "filename": filename,
                            "status": "DUPLICATE",
                        }
                    )

                    progress.progress(
                        (index + 1)
                        / len(uploaded_files)
                    )

                    continue


                # ============================================
                # EXTRACT TEXT
                # ============================================

                (
                    extracted_text,
                    extraction_status
                ) = extract_text(
                    file_bytes,
                    filename
                )


                # ============================================
                # CREATE BLIND CANDIDATE ID
                # ============================================

                blind_id = (
                    f"CAND-"
                    f"{uuid.uuid4().hex[:8].upper()}"
                )


                candidate_id = create_candidate(
                    blind_id
                )


                # ============================================
                # CREATE STORED FILENAME
                # ============================================

                file_extension = (
                    Path(filename)
                    .suffix
                    .lower()
                )


                stored_filename = (
                    f"{blind_id}_"
                    f"{uuid.uuid4().hex}"
                    f"{file_extension}"
                )


                stored_path = (
                    RESUME_DIR
                    / stored_filename
                )


                # ============================================
                # SAVE ORIGINAL FILE
                # ============================================

                stored_path.write_bytes(
                    file_bytes
                )


                # ============================================
                # SAVE RESUME INFORMATION
                # ============================================

                resume_id = create_resume(
                    candidate_id=candidate_id,

                    original_filename=filename,

                    stored_filename=stored_filename,

                    stored_path=str(
                        stored_path
                    ),

                    file_hash=file_hash,

                    extracted_text=extracted_text,

                    extraction_status=(
                        extraction_status
                    ),

                    parser_version=(
                        PARSER_VERSION
                    ),
                )


                # ============================================
                # CREATE APPLICATION
                # ============================================

                application_id = (
                    create_application(
                        candidate_id=candidate_id,

                        job_id=selected_job_id,

                        resume_id=resume_id,
                    )
                )


                # ============================================
                # CHECK APPLICATION RESULT
                # ============================================

                if application_id is None:

                    skipped += 1

                    results.append(
                        {
                            "filename": filename,
                            "status": (
                                "ALREADY APPLIED"
                            ),
                        }
                    )

                else:

                    successful += 1

                    results.append(
                        {
                            "filename": filename,

                            "status": (
                                extraction_status
                            ),

                            "blind_id": blind_id,
                        }
                    )


            except Exception as error:

                failed += 1

                results.append(
                    {
                        "filename": filename,

                        "status": (
                            f"ERROR: {error}"
                        ),
                    }
                )


            # ================================================
            # UPDATE PROGRESS BAR
            # ================================================

            progress.progress(
                (index + 1)
                / len(uploaded_files)
            )


        # ====================================================
        # SUMMARY
        # ====================================================

        st.divider()

        col1, col2, col3 = st.columns(3)


        with col1:

            st.metric(
                "Processed",
                successful
            )


        with col2:

            st.metric(
                "Skipped",
                skipped
            )


        with col3:

            st.metric(
                "Failed",
                failed
            )


        # ====================================================
        # PROCESSING RESULTS
        # ====================================================

        st.subheader(
            "Processing Results"
        )


        for result in results:

            status = result["status"]


            if status == "SUCCESS":

                st.success(
                    f"{result['filename']} "
                    f"→ {result['blind_id']}"
                )


            elif status == "LOW_TEXT_WARNING":

                st.warning(
                    f"{result['filename']} "
                    "→ Low text / possible scanned document"
                )


            elif (
                status == "DUPLICATE"
                or status == "ALREADY APPLIED"
            ):

                st.info(
                    f"{result['filename']} "
                    f"→ {status}"
                )


            else:

                st.error(
                    f"{result['filename']} "
                    f"→ {status}"
                )


# ============================================================
# CURRENT APPLICATIONS
# ============================================================

st.divider()

st.subheader(
    "Current Applications"
)


applications = get_job_applications(
    selected_job_id
)


if not applications:

    st.info(
        "No applications have been uploaded "
        "for this job yet."
    )


else:

    for application in applications:

        with st.container(
            border=True
        ):

            col1, col2, col3 = st.columns(3)


            with col1:

                st.write(
                    f"**{application['blind_id']}**"
                )


            with col2:

                st.write(
                    application[
                        "original_filename"
                    ]
                )


            with col3:

                st.write(
                    application[
                        "extraction_status"
                    ]
                )