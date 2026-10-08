"""Streamlit page: run the resume NER pipeline and inspect the results."""

from __future__ import annotations

from collections import Counter, defaultdict

import streamlit as st

from db import (
    create_resume_entity,
    delete_resume_entities,
    get_all_jobs,
    get_all_resumes,
    get_job_resumes,
    get_resume_entities,
)
from resume_ner import MODEL_NAME, NER_VERSION, extract_resume_entities

MODE_JOB = "Resumes for a Job"
MODE_ALL = "All Stored Resumes"


# Loading resumes

def select_resumes() -> list:
    """Let the user choose which resumes to analyze and return them."""
    mode = st.radio(
        "Choose resumes to analyze",
        [MODE_JOB, MODE_ALL],
        horizontal=True,
    )

    if mode == MODE_ALL:
        return get_all_resumes()

    jobs = get_all_jobs()
    if not jobs:
        st.warning("No jobs have been created yet.")
        st.stop()

    job_options = {
        f"#{job['job_id']} — {job['job_title']} [{job['status']}]": job["job_id"]
        for job in jobs
    }
    selected_label = st.selectbox("Select Job", list(job_options))

    return get_job_resumes(job_options[selected_label])


# Running NER

def analyze_resume(resume) -> int | None:
    """
    Run NER on one resume and save the entities.

    Returns the number of entities saved, or None if the resume has no text.
    """
    text = resume["extracted_text"] or ""
    if not text.strip():
        return None

    resume_id = resume["resume_id"]

    # Replace any results from a previous run.
    delete_resume_entities(resume_id)

    entities = extract_resume_entities(text)["entities"]

    for entity in entities:
        create_resume_entity(
            resume_id=resume_id,
            entity_text=entity["text"],
            entity_label=entity["label"],
            start_char=entity["start"],
            end_char=entity["end"],
            confidence=entity["confidence"],
            source=entity["source"],
        )

    return len(entities)


def run_ner(resumes: list) -> None:
    """Analyze every resume, showing progress and a final summary."""
    progress = st.progress(0)
    processed = 0
    failed = 0
    total_entities = 0

    for index, resume in enumerate(resumes, start=1):
        try:
            entity_count = analyze_resume(resume)

            if entity_count is None:  # no text to analyze
                failed += 1
            else:
                processed += 1
                total_entities += entity_count

        except Exception as error:
            failed += 1
            st.error(f"Error processing {resume['original_filename']}: {error}")

        progress.progress(index / len(resumes))

    st.success(f"NER completed. {processed} resume(s) processed.")

    if failed:
        st.warning(f"{failed} resume(s) could not be processed.")

    st.info(f"{total_entities} total entities extracted.")


# Showing results

def show_resume_info(resume) -> None:
    """Show the resume's key details and its raw extracted text."""
    col1, col2, col3 = st.columns(3)
    col1.metric("Blind Candidate ID", resume["blind_id"])
    col2.metric("Resume ID", resume["resume_id"])
    col3.metric("Extraction Status", resume["extraction_status"])

    with st.expander("View Raw Extracted Text"):
        st.text_area(
            "Resume Text",
            resume["extracted_text"] or "",
            height=400,
            disabled=True,
        )


def show_entity_summary(entities: list) -> None:
    """Show how many entities were found for each label."""
    counts = sorted(Counter(e["entity_label"] for e in entities).items())

    # At most 4 metrics per row.
    columns = st.columns(min(len(counts), 4))

    for index, (label, count) in enumerate(counts):
        columns[index % len(columns)].metric(label, count)


def show_entity_details(entities: list) -> None:
    """Show every entity, grouped by label in collapsible sections."""
    grouped = defaultdict(list)
    for entity in entities:
        grouped[entity["entity_label"]].append(entity)

    for label in sorted(grouped):
        with st.expander(f"{label} ({len(grouped[label])})"):
            for entity in grouped[label]:
                confidence = entity["confidence"]
                confidence_text = (
                    "Not provided" if confidence is None else f"{confidence:.0%}"
                )

                st.write(f"**{entity['entity_text']}**")
                st.caption(
                    f"Source: {entity['source']} | Confidence: {confidence_text}"
                )


# Page layout

def main() -> None:
    st.title("Analyze Resumes")
    st.caption(
        "Extract structured information from candidate resumes "
        "using the current resume NER pipeline."
    )
    st.info(
        "This is the baseline NER stage. "
        "It extracts information but does not rank candidates "
        "or calculate scores yet."
    )

    resumes = select_resumes()

    if not resumes:
        st.info("No resumes are available for analysis yet.")
        st.stop()

    st.metric("Resumes Available", len(resumes))
    st.divider()

    if st.button("Run NER on Resumes", type="primary"):
        run_ner(resumes)

    st.divider()

    # Inspect one resume
    st.subheader("Resume Results")

    resume_options = {
        f"{resume['blind_id']} — {resume['original_filename']}": resume
        for resume in resumes
    }
    selected_label = st.selectbox("Select a resume to inspect", list(resume_options))
    selected_resume = resume_options[selected_label]

    show_resume_info(selected_resume)

    entities = get_resume_entities(selected_resume["resume_id"])

    if not entities:
        st.warning(
            "No NER results found for this resume. "
            "Click 'Run NER on Resumes' above."
        )
        st.stop()

    st.divider()
    st.subheader("Extracted Information")
    show_entity_summary(entities)

    st.divider()
    st.subheader("Entity Details")
    show_entity_details(entities)

    st.divider()
    st.caption(f"NER model: {MODEL_NAME}")
    st.caption(f"NER pipeline version: {NER_VERSION}")


main()