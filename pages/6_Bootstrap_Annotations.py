"""
Streamlit page: generate and inspect bootstrap annotation suggestions.

The page has three parts:
    1. A button that generates suggested labels from stored resumes.
    2. A summary of the last generation run.
    3. A viewer to inspect the suggestions for one resume.

The suggestions are automatic and have NOT been verified by a human.
"""

from __future__ import annotations

import json
from typing import Any

import streamlit as st

from bootstrap import OUTPUT_PATH, generate_bootstrap_dataset

# One line of the generated .jsonl file (one resume).
Record = dict[str, Any]


# Reading the generated file

def load_bootstrap_records() -> list[Record]:
    """Read the generated .jsonl file (one JSON record per line)."""
    if not OUTPUT_PATH.exists():
        return []

    with OUTPUT_PATH.open("r", encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


# Section 1: generate labels

def show_generate_section() -> None:
    """Show the 'Generate' button and run the generation when clicked."""
    st.subheader("1. Generate Initial Labels")
    st.write(
        "The system will read the extracted resume text already "
        "saved in the local database. It will not require you "
        "to upload the resumes again."
    )

    if not st.button("Generate Bootstrap Labels", type="primary"):
        return

    with st.spinner("Generating annotation suggestions..."):
        try:
            # Keep the report in session state so it survives page reruns.
            st.session_state["bootstrap_report"] = generate_bootstrap_dataset()
            st.success("Bootstrap dataset generated successfully.")
        except Exception as error:
            st.error(f"Bootstrap generation failed: {error}")


# Section 2: generation summary

def show_report(report: dict[str, Any]) -> None:
    """Show the counts from the last generation run."""
    st.divider()
    st.subheader("2. Generation Summary")

    col1, col2, col3 = st.columns(3)
    col1.metric("Resumes in Database", report["total_resumes_in_database"])
    col2.metric("Resumes Processed", report["resumes_in_dataset"])
    col3.metric("Suggested Entities", report["total_suggested_entities"])

    st.write(
        "**Resumes skipped due to empty/short text:** "
        f"{report['skipped_empty_or_short']}"
    )
    st.write(
        "**Resumes with no automatically suggested entities:** "
        f"{report['resumes_without_suggestions']}"
    )

    st.write("**Local output file:**")
    st.code(report["output_path"])

    st.write("Suggestions by entity type:")
    st.json(report["entities_by_label"])


# Section 3: inspect one resume

def show_entity_table(entities: list[dict[str, Any]]) -> None:
    """Show the suggested entities as a table."""
    st.subheader("Suggested Entity Labels")

    if not entities:
        st.info(
            "No automatic entity suggestions were produced "
            "for this resume. It may still be useful for "
            "manual annotation."
        )
        return

    rows = [
        {
            "Text": entity["text"],
            "Label": entity["label"],
            "Start": entity["start"],
            "End": entity["end"],
            "Source": entity["source"],
            "Rule Strength": entity["rule_strength"],
        }
        for entity in entities
    ]

    st.dataframe(rows, use_container_width=True, hide_index=True)


def show_section_hints(hints: list[dict[str, Any]]) -> None:
    """Show lines found inside project, course and experience sections."""
    with st.expander("View project/course/experience section hints"):
        if not hints:
            st.info(
                "No recognized project, course or experience "
                "sections were found. Section headings may "
                "vary between resume formats."
            )
            return

        for hint in hints:
            st.markdown(f"**{hint['section']}**")
            st.write(hint["text"])
            st.caption(f"Character range: {hint['start']}–{hint['end']}")
            st.divider()


def show_record(record: Record) -> None:
    """Show everything the bootstrap produced for one resume."""
    col1, col2, col3 = st.columns(3)
    col1.metric("Suggested Entities", len(record["entities"]))
    col2.metric("Section Hints", len(record["section_hints"]))
    col3.metric("Review Status", record["review_status"])

    show_entity_table(record["entities"])
    show_section_hints(record["section_hints"])

    with st.expander("View raw resume text (local review only)"):
        st.text_area(
            "Extracted Resume Text",
            record["text"],
            height=350,
            disabled=True,
            key=f"bootstrap_raw_{record['resume_id']}",  # unique key per resume
        )

    st.caption(
        "All displayed resume content is local to this prototype. "
        "Do not upload the generated annotation dataset to GitHub "
        "because it contains resume text."
    )


# Page layout

def main() -> None:
    st.title("Bootstrap Annotations")
    st.caption(
        "Generate initial automatic annotation suggestions "
        "from stored candidate resumes."
    )
    st.warning(
        "Bootstrap labels are automatically generated suggestions. "
        "They have not been verified by a human and must not be used "
        "as confirmed training labels or as candidate ranking scores."
    )

    show_generate_section()

    report = st.session_state.get("bootstrap_report")
    if report:
        show_report(report)

    # Load after generating, so a new file shows up straight away.
    records = load_bootstrap_records()

    if not records:
        st.info(
            "No bootstrap dataset exists yet. "
            "Click 'Generate Bootstrap Labels' above after "
            "you have stored resumes in the application."
        )
        return

    st.divider()
    st.subheader("3. Inspect Bootstrap Suggestions")
    st.write(
        "Choose a blind candidate ID to inspect the "
        "suggested labels. Inspection here does not mean "
        "the annotations have been approved."
    )

    options = {
        f"{record['blind_id']} (Resume ID: {record['resume_id']})": record
        for record in records
    }
    selected_label = st.selectbox("Select a resume", list(options))

    show_record(options[selected_label])


main()