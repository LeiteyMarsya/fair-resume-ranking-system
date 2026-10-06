import streamlit as st

from db import (
    get_all_jobs,
    get_job,
    update_job_status,
)


# ============================================================
# PAGE TITLE
# ============================================================

st.title("Manage Jobs")


# ============================================================
# GET JOBS
# ============================================================

jobs = get_all_jobs()


# ============================================================
# NO JOBS
# ============================================================

if not jobs:

    st.info(
        "No jobs have been created yet. "
        "Go to 'Create Job' first."
    )

    st.stop()


# ============================================================
# CREATE DROPDOWN
# ============================================================

job_options = {
    (
        f"#{job['job_id']} — "
        f"{job['job_title']} "
        f"({job['seniority_level']}) "
        f"[{job['status']}]"
    ):
    job["job_id"]

    for job in jobs
}


selected_label = st.selectbox(
    "Select Job",
    list(job_options.keys())
)


selected_job_id = job_options[
    selected_label
]


# ============================================================
# GET SELECTED JOB
# ============================================================

job = get_job(
    selected_job_id
)


st.divider()


# ============================================================
# SUMMARY
# ============================================================

col1, col2, col3 = st.columns(3)


with col1:

    st.metric(
        "Job ID",
        job["job_id"]
    )


with col2:

    st.metric(
        "Job Level",
        job["seniority_level"]
    )


with col3:

    st.metric(
        "Status",
        job["status"]
    )


# ============================================================
# JOB INFORMATION
# ============================================================

st.subheader(
    job["job_title"]
)


st.write(
    f"**Created:** {job['created_at']}"
)


if job["source_filename"]:

    st.write(
        f"**Source file:** "
        f"{job['source_filename']}"
    )


st.text_area(
    "Job Description",
    job["description"],
    height=400,
    disabled=True
)


# ============================================================
# STATUS MANAGEMENT
# ============================================================

st.divider()

st.subheader(
    "Job Status"
)


status_options = [
    "DRAFT",
    "ACTIVE",
    "CLOSED"
]


current_index = status_options.index(
    job["status"]
)


new_status = st.selectbox(
    "Change status",
    status_options,
    index=current_index
)


if st.button(
    "Update Status",
    type="primary"
):

    update_job_status(
        selected_job_id,
        new_status
    )

    st.success(
        f"Job status changed to {new_status}."
    )

    st.rerun()