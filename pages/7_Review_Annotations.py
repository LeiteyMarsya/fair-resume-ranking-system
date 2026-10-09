
from __future__ import annotations

from datetime import datetime, timezone
import uuid

import streamlit as st

from annotation_review import (
    ALLOWED_LABELS,
    BOOTSTRAP_PATH,
    REVIEWED_PATH,
    find_nth_occurrence,
    find_occurrences,
    find_overlaps,
    load_review_workspace,
    locate_edited_entity,
    save_reviewed_record,
)


# Page title

st.title("Review Annotations")

st.caption(
    "Correct automatic entity suggestions before using "
    "the annotations to train a resume-specific NER model."
)


# Important information

st.warning(
    "Only accept an entity if both its text boundaries "
    "and label are correct. Rejected suggestions will not "
    "be used as positive training annotations."
)


# Check bootstrap dataset

if not BOOTSTRAP_PATH.exists():

    st.error(
        "The bootstrap dataset was not found."
    )

    st.write(
        "Please finish Part 4A first, then generate "
        "bootstrap_candidates.jsonl."
    )

    st.code(
        "python bootstrap.py"
    )

    st.stop()


# Load workspace

try:

    records = load_review_workspace()

except Exception as error:

    st.error(
        f"Could not load annotation data: {error}"
    )

    st.stop()


if not records:

    st.info(
        "No resumes were found in the bootstrap dataset. "
        "Upload and process resumes first."
    )

    st.stop()


# Review progress

st.subheader(
    "Annotation Progress"
)


reviewed_count = sum(
    1
    for record in records
    if record.get("review_status") == "REVIEWED"
)


in_progress_count = sum(
    1
    for record in records
    if record.get("review_status") == "IN_PROGRESS"
)


pending_count = sum(
    1
    for record in records
    if record.get("review_status", "PENDING")
    not in {"REVIEWED", "IN_PROGRESS"}
)


col1, col2, col3 = st.columns(3)


with col1:

    st.metric(
        "Pending",
        pending_count
    )


with col2:

    st.metric(
        "In Progress",
        in_progress_count
    )


with col3:

    st.metric(
        "Completed Reviews",
        reviewed_count
    )


# Summary table

with st.expander(
    "View review status for all resumes"
):

    status_rows = []

    for record in records:

        review_entities = record.get(
            "review_entities",
            [],
        )

        accepted_count = sum(
            1
            for entity in review_entities
            if entity.get("accepted", False)
        )

        status_rows.append(
            {
                "Blind ID": record.get(
                    "blind_id",
                    "UNKNOWN",
                ),

                "Resume ID": record.get(
                    "resume_id"
                ),

                "Status": record.get(
                    "review_status",
                    "PENDING",
                ),

                "Accepted Entities": accepted_count,
            }
        )

    st.dataframe(
        status_rows,
        use_container_width=True,
        hide_index=True,
    )


st.divider()


# Resume selection

record_options = {}

for record in records:

    label = (
        f"{record.get('blind_id', 'UNKNOWN')} "
        f"(Resume ID: {record.get('resume_id')})"
        f" [{record.get('review_status', 'PENDING')}]"
    )

    record_options[label] = record


selected_label = st.selectbox(
    "Select a resume to review",
    list(record_options.keys()),
)


record = record_options[
    selected_label
]


resume_id = record["resume_id"]

resume_text = record.get(
    "text",
    "",
)


# Resume information

st.subheader(
    f"Resume: {record.get('blind_id', 'UNKNOWN')}"
)


st.write(
    f"**Resume ID:** {resume_id}"
)


st.write(
    f"**Current status:** "
    f"{record.get('review_status', 'PENDING')}"
)


# Show source text

with st.expander(
    "View original extracted resume text",
    expanded=True,
):

    st.text_area(
        "Resume text",
        value=resume_text,
        height=350,
        disabled=True,
        key=f"source_text_{resume_id}",
    )


# Show section hints

section_hints = record.get(
    "section_hints",
    [],
)


if section_hints:

    with st.expander(
        "View project, course and experience section hints"
    ):

        st.caption(
            "These are heuristic section hints, not confirmed "
            "entity labels. Use them to help find missing entities."
        )

        for hint in section_hints:

            st.markdown(
                f"**{hint['section']}**"
            )

            st.write(
                hint["text"]
            )

            st.caption(
                f"Character range: "
                f"{hint['start']}–{hint['end']}"
            )


# Current review items

review_entities = record.get(
    "review_entities",
    [],
)


st.divider()

st.subheader(
    "Edit automatic suggestions"
)


st.write(
    "For each suggestion, keep it only if the text and "
    "label are correct. You can also edit the text or "
    "change its category."
)


# Review form: save all edits together.

with st.form(
    key=f"review_form_{resume_id}"
):

    edited_items = []


    # Existing suggestions

    if review_entities:

        for index, entity in enumerate(
            review_entities
        ):

            review_id = str(
                entity.get(
                    "review_id",
                    f"entity_{index}",
                )
            )


            st.markdown(
                f"**Suggestion {index + 1}**"
            )


            keep_col, text_col, label_col = st.columns(
                [1, 4, 2]
            )


            with keep_col:

                accepted = st.checkbox(
                    "Keep",

                    value=bool(
                        entity.get(
                            "accepted",
                            True,
                        )
                    ),

                    key=(
                        f"keep_{resume_id}_{review_id}"
                    ),

                    help=(
                        "Uncheck if this suggestion is incorrect "
                        "or should not be used as a positive "
                        "training annotation."
                    ),
                )


            with text_col:

                edited_text = st.text_input(
                    "Entity text",

                    value=entity.get(
                        "text",
                        "",
                    ),

                    key=(
                        f"text_{resume_id}_{review_id}"
                    ),
                )


            with label_col:

                current_label = entity.get(
                    "label",
                    "SKILL",
                )

                if current_label not in ALLOWED_LABELS:
                    current_label = "SKILL"

                label_index = ALLOWED_LABELS.index(
                    current_label
                )

                edited_label = st.selectbox(
                    "Entity label",

                    ALLOWED_LABELS,

                    index=label_index,

                    key=(
                        f"label_{resume_id}_{review_id}"
                    ),
                )


            st.caption(
                f"Original source: "
                f"{entity.get('source', 'UNKNOWN')} | "
                f"Original span: "
                f"{entity.get('start', '?')}–"
                f"{entity.get('end', '?')}"
            )


            edited_items.append(
                {
                    "original": entity,

                    "review_id": review_id,

                    "accepted": accepted,

                    "text": edited_text,

                    "label": edited_label,
                }
            )


            st.divider()


    else:

        st.info(
            "No automatic suggestions were generated "
            "for this resume. You can add entities manually below."
        )


    # Add missing entities

    st.subheader(
        "Add missing entities"
    )


    st.write(
        "Copy an exact phrase from the original resume text, "
        "select the correct label, and choose which occurrence "
        "it refers to. Empty rows are ignored."
    )


    manual_items = []


    for slot in range(1, 4):

        st.markdown(
            f"**Manual entity {slot}**"
        )


        text_col, label_col, occurrence_col = st.columns(
            [4, 2, 1]
        )


        with text_col:

            manual_text = st.text_input(
                "Exact phrase from resume",

                value="",

                key=(
                    f"manual_text_{resume_id}_{slot}"
                ),

                placeholder=(
                    "Example: Database Management"
                ),
            )


        with label_col:

            manual_label = st.selectbox(
                "Label",

                ALLOWED_LABELS,

                index=ALLOWED_LABELS.index(
                    "COURSE"
                ),

                key=(
                    f"manual_label_{resume_id}_{slot}"
                ),
            )


        with occurrence_col:

            occurrence_number = st.number_input(
                "Occurrence",

                min_value=1,

                max_value=100,

                value=1,

                step=1,

                key=(
                    f"manual_occurrence_{resume_id}_{slot}"
                ),

                help=(
                    "Choose 1 for the first occurrence, "
                    "2 for the second, and so on."
                ),
            )


        manual_items.append(
            {
                "text": manual_text,

                "label": manual_label,

                "occurrence": int(
                    occurrence_number
                ),
            }
        )


    # Review completion

    st.divider()

    existing_status = record.get(
        "review_status",
        "PENDING",
    )


    mark_complete = st.checkbox(
        "I have reviewed the suggestions and manually checked "
        "the relevant entities for this resume.",

        value=(
            existing_status == "REVIEWED"
        ),

        key=f"complete_{resume_id}",
    )


    st.caption(
        "Mark this complete only after checking the existing "
        "suggestions and adding or rejecting relevant entities "
        "as appropriate."
    )


    save_button = st.form_submit_button(
        "Save Annotation Review",
        type="primary",
    )


# Process submission

if save_button:

    errors = []

    updated_entities = []


    # Process existing items

    for item in edited_items:

        original = item["original"]

        # Rejected suggestion

        if not item["accepted"]:
            rejected = dict(
                original
            )

            rejected["accepted"] = False

            rejected["reviewed_by_human"] = True

            rejected["review_action"] = "REJECTED"

            updated_entities.append(
                rejected
            )

            continue


        # Accepted suggestion

        edited_text = (
            item["text"].strip()
        )

        if not edited_text:

            errors.append(
                f"Suggestion {item['review_id']}: "
                "accepted entity text cannot be empty."
            )

            continue


        previous_start = int(
            original.get("start", 0)
        )


        resolved = locate_edited_entity(
            original_text=resume_text,

            edited_phrase=edited_text,

            previous_start=previous_start,
        )


        if resolved is None:

            errors.append(
                f"Suggestion {item['review_id']}: "
                f"'{edited_text}' could not be found in the "
                "original resume. Copy the exact phrase from "
                "the source text or reject the suggestion."
            )

            continue


        start, end, source_text = resolved


        updated = dict(
            original
        )


        updated.update(
            {
                "review_id": item["review_id"],

                "start": start,

                "end": end,

                # Store the exact text found in the resume.
                "text": source_text,

                "label": item["label"],

                "accepted": True,

                "reviewed_by_human": True,

                "review_action": "ACCEPTED_OR_CORRECTED",
            }
        )


        updated_entities.append(
            updated
        )


    # Process manual items

    manual_added_count = 0

    for manual_index, item in enumerate(
        manual_items,
        start=1,
    ):

        phrase = item["text"].strip()


        # Ignore empty manual-entry slots.
        if not phrase:
            continue


        resolved_span = find_nth_occurrence(
            text=resume_text,

            phrase=phrase,

            occurrence_number=item["occurrence"],
        )


        if resolved_span is None:

            occurrence_count = len(
                find_occurrences(
                    resume_text,
                    phrase,
                )
            )

            errors.append(
                f"Manual entity {manual_index}: "
                f"could not find occurrence "
                f"{item['occurrence']} of '{phrase}'. "
                f"Matching occurrences found: "
                f"{occurrence_count}. Copy the exact phrase "
                "from the original text and check the occurrence."
            )

            continue


        start, end = resolved_span

        source_text = resume_text[
            start:end
        ]


        manual_entity = {
            "review_id": (
                f"manual_{uuid.uuid4().hex[:12]}"
            ),

            "start": start,

            "end": end,

            "text": source_text,

            "label": item["label"],

            "source": "MANUAL_ANNOTATION",

            "rule_strength": None,

            "accepted": True,

            "origin": "MANUAL",

            "reviewed_by_human": True,

            "review_action": "MANUALLY_ADDED",
        }


        updated_entities.append(
            manual_entity
        )

        manual_added_count += 1


    # Remove exact duplicates

    unique_entities = []

    seen_accepted = set()

    for entity in updated_entities:

        if not entity.get(
            "accepted",
            False,
        ):

            unique_entities.append(
                entity
            )

            continue


        key = (
            entity["start"],
            entity["end"],
            entity["label"],
        )


        if key in seen_accepted:
            continue


        seen_accepted.add(key)

        unique_entities.append(
            entity
        )


    # Validate overlapping entities

    overlaps = find_overlaps(
        unique_entities
    )


    if overlaps:

        for first, second in overlaps:

            errors.append(
                "Overlapping accepted annotations: "
                f"'{first['text']}' ({first['label']}) and "
                f"'{second['text']}' ({second['label']}). "
                "Correct the spans or uncheck the incorrect "
                "annotation before saving."
            )


    # Validate source offsets

    for entity in unique_entities:

        if not entity.get(
            "accepted",
            False,
        ):
            continue


        start = entity["start"]
        end = entity["end"]


        if not (
            0 <= start < end <= len(resume_text)
        ):

            errors.append(
                f"Invalid offsets for '{entity['text']}'."
            )

            continue


        if resume_text[start:end] != entity["text"]:

            errors.append(
                f"Text offsets do not match the original "
                f"resume for '{entity['text']}'."
            )


    # Show validation errors

    if errors:

        st.error(
            "The annotations were not saved because "
            "there are problems to correct."
        )


        for error in errors:

            st.write(
                f"- {error}"
            )


        st.stop()


    # Save review

    saved_record = dict(
        record
    )


    saved_record["review_entities"] = (
        unique_entities
    )


    saved_record["review_status"] = (
        "REVIEWED"
        if mark_complete
        else "IN_PROGRESS"
    )


    saved_record["review_complete"] = (
        bool(mark_complete)
    )


    saved_record["reviewed_at"] = (
        datetime.now(
            timezone.utc
        ).isoformat()
    )


    saved_record["annotation_schema_version"] = (
        "1.0"
    )


    try:

        save_reviewed_record(
            saved_record
        )


        st.success(
            "Annotation review saved successfully."
        )


        st.metric(
            "Accepted entities",
            sum(
                1
                for entity in unique_entities
                if entity.get("accepted", False)
            )
        )


        st.metric(
            "Manually added entities",
            manual_added_count
        )


        if mark_complete:

            st.info(
                "This resume is marked REVIEWED. "
                "Its accepted entities can be considered "
                "for the training dataset after quality checks."
            )

        else:

            st.info(
                "This resume is saved as IN_PROGRESS. "
                "Continue reviewing it before using it as a "
                "completed training example."
            )


        st.rerun()


    except Exception as error:

        st.error(
            f"Could not save the review: {error}"
        )


# Footer

st.divider()

st.caption(
    f"Bootstrap source: {BOOTSTRAP_PATH.name}"
)

st.caption(
    f"Reviewed dataset: {REVIEWED_PATH.name}"
)

st.caption(
    "The original bootstrap dataset is not overwritten. "
    "Only reviewed annotations are written to the separate "
    "reviewed dataset."
)