
import streamlit as st

from job_occupation_esco_review import (
    get_occupation_review_counts,
    get_pending_occupation_proposals,
    get_job_requirements_for_occupation_review,
    save_occupation_review,
)


# ============================================================
# PAGE TITLE
# ============================================================

st.title("Review ESCO Occupations")

st.caption(
    "Review automatically proposed ESCO occupations "
    "before accepting them as job classification mappings."
)


# ============================================================
# IMPORTANT INFORMATION
# ============================================================

st.info(
    "ESCO occupation mappings are suggestions generated "
    "by the system. Recruiters must manually review each "
    "proposal before it can be approved."
)


# ============================================================
# LOAD REVIEW COUNTS
# ============================================================

try:

    counts = get_occupation_review_counts()

except Exception as error:

    st.error(
        f"Could not load occupation review statistics: {error}"
    )

    st.stop()


# ============================================================
# REVIEW DASHBOARD
# ============================================================

st.subheader("Occupation Review Progress")

col1, col2, col3 = st.columns(3)

with col1:

    st.metric(
        "Pending",
        counts["pending_count"]
    )

with col2:

    st.metric(
        "Approved",
        counts["approved_count"]
    )

with col3:

    st.metric(
        "Rejected",
        counts["rejected_count"]
    )


st.divider()


# ============================================================
# LOAD PENDING PROPOSALS
# ============================================================

try:

    proposals = get_pending_occupation_proposals()

except Exception as error:

    st.error(
        f"Could not load pending occupation proposals: {error}"
    )

    st.stop()


if not proposals:

    st.success(
        "There are currently no pending ESCO occupation "
        "proposals requiring review."
    )

    st.stop()


# ============================================================
# SELECT PENDING PROPOSAL
# ============================================================

st.subheader("Pending Occupation Proposals")

proposal_options = {

    (
        f"Job #{proposal['job_id']} - "
        f"{proposal['job_title']} - "
        f"{proposal['preferred_label']}"
    ): proposal["mapping_id"]

    for proposal in proposals

}


selected_label = st.selectbox(
    "Select an occupation proposal",
    list(proposal_options.keys())
)


selected_mapping_id = proposal_options[
    selected_label
]


selected_proposal = next(

    proposal
    for proposal in proposals
    if proposal["mapping_id"] == selected_mapping_id

)


# ============================================================
# ORIGINAL JOB INFORMATION
# ============================================================

st.divider()

st.subheader("Original Job Information")

st.write(
    f"**Job Title:** {selected_proposal['job_title']}"
)

st.write(
    f"**Seniority Level:** "
    f"{selected_proposal['seniority_level']}"
)

st.write(
    f"**Job ID:** {selected_proposal['job_id']}"
)

st.markdown("**Complete Job Description**")

st.write(
    selected_proposal["description"]
    or "No job description available."
)

# ============================================================
# JOB REQUIREMENTS EVIDENCE
# ============================================================

st.divider()

st.subheader("Job Requirements Evidence")

try:

    requirements_result = (
        get_job_requirements_for_occupation_review(
            selected_proposal["job_id"]
        )
    )

    if requirements_result["status"] != "SUCCESS":

        st.warning(
            "Job requirements could not be retrieved."
        )

    else:

        confirmed = requirements_result["confirmed"]
        unconfirmed = requirements_result["unconfirmed"]

        st.write(
            f"**Total Requirements:** "
            f"{requirements_result['total_requirements']}"
        )

        # ----------------------------------------------------
        # CONFIRMED REQUIREMENTS
        # ----------------------------------------------------

        st.markdown("**Recruiter-Confirmed Requirements**")

        if not confirmed:

            st.info(
                "No recruiter-confirmed requirements "
                "are currently available for this job."
            )

        else:

            for index, requirement in enumerate(confirmed, 1):

                with st.expander(
                    f"Confirmed Requirement {index}: "
                    f"{requirement['requirement_text']}"
                ):

                    st.write(
                        f"**Category:** {requirement['category']}"
                    )

                    st.write(
                        f"**Type:** {requirement['requirement_type']}"
                    )

                    st.write(
                        f"**Mandatory:** "
                        f"{'Yes' if requirement['mandatory'] else 'No'}"
                    )

                    st.write(
                        f"**Importance Weight:** "
                        f"{requirement['importance_weight']}"
                    )

                    st.write(
                        f"**Confidence:** "
                        f"{requirement['confidence']}"
                    )

                    st.markdown("**Related ESCO Skills**")

                    if requirement["esco_skills"]:

                        for skill in requirement["esco_skills"]:

                            st.write(
                                f"**{skill['skill_label'] or skill['skill_uri']}**"
                            )

                            score = skill["mapping_score"]

                            st.caption(
                                f"Mapping Status: "
                                f"{skill['mapping_status']} | "
                                f"Method: "
                                f"{skill['mapping_method'] or 'N/A'}"
                            )

                            st.caption(
                                f"Mapping Score: "
                                f"{score:.2f}"
                                if score is not None
                                else "Mapping Score: N/A"
                            )

                            st.caption(
                                f"Reviewed: "
                                f"{'Yes' if skill['reviewed'] else 'No'}"
                            )

                    else:

                        st.caption(
                            "No ESCO skill mapping is available."
                        )

        # ----------------------------------------------------
        # UNCONFIRMED REQUIREMENTS
        # ----------------------------------------------------

        st.markdown("**Unconfirmed Requirements**")

        if not unconfirmed:

            st.caption(
                "No unconfirmed requirements."
            )

        else:

            st.warning(
                "These requirements have not been verified "
                "by the recruiter. Treat them as supporting "
                "information, not confirmed evidence."
            )

            for index, requirement in enumerate(unconfirmed, 1):

                with st.expander(
                    f"Unconfirmed Requirement {index}: "
                    f"{requirement['requirement_text']}"
                ):

                    st.write(
                        f"**Category:** {requirement['category']}"
                    )

                    st.write(
                        f"**Type:** {requirement['requirement_type']}"
                    )

                    st.write(
                        f"**Mandatory:** "
                        f"{'Yes' if requirement['mandatory'] else 'No'}"
                    )

                    if requirement["esco_skills"]:

                        st.markdown("**Related ESCO Skills**")

                        for skill in requirement["esco_skills"]:

                            st.write(
                                f"**{skill['skill_label'] or skill['skill_uri']}**"
                            )

                            score = skill["mapping_score"]

                            st.caption(
                                f"Mapping Status: "
                                f"{skill['mapping_status']} | "
                                f"Method: "
                                f"{skill['mapping_method'] or 'N/A'}"
                            )

                            st.caption(
                                f"Mapping Score: "
                                f"{score:.2f}"
                                if score is not None
                                else "Mapping Score: N/A"
                            )

                            st.caption(
                                f"Reviewed: "
                                f"{'Yes' if skill['reviewed'] else 'No'}"
                            )

except Exception as error:

    st.error(
        f"Could not display job requirements: {error}"
    )

# ============================================================
# PROPOSED ESCO OCCUPATION
# ============================================================

st.divider()

st.subheader("Proposed ESCO Occupation")

st.write(
    f"**Preferred Label:** "
    f"{selected_proposal['preferred_label']}"
)

st.write(
    f"**ESCO Code:** "
    f"{selected_proposal['code'] or 'Not available'}"
)

st.write(
    f"**ISCO Group:** "
    f"{selected_proposal['isco_group'] or 'Not available'}"
)

st.write(
    f"**Occupation Definition:** "
    f"{selected_proposal['definition'] or 'Not available'}"
)

if selected_proposal["scope_note"]:

    with st.expander("View ESCO Scope Note"):

        st.write(
            selected_proposal["scope_note"]
        )


# ============================================================
# MAPPING INFORMATION
# ============================================================

st.divider()

st.subheader("Mapping Information")

col1, col2, col3 = st.columns(3)

with col1:

    st.metric(
        "Matching Method",
        selected_proposal["mapping_method"] or "N/A"
    )

with col2:

    score = selected_proposal["mapping_score"]

    st.metric(
        "Matching Score",
        f"{score:.2f}" if score is not None else "N/A"
    )

with col3:

    st.metric(
        "Current Status",
        selected_proposal["mapping_status"]
    )


st.caption(
    "A matching score indicates similarity, "
    "not guaranteed occupational correctness."
)


# ============================================================
# RECRUITER REVIEW DECISION
# ============================================================

st.divider()

st.subheader("Recruiter Decision")

st.info(
    """
    Before making your decision, carefully evaluate:

    1. Whether the proposed ESCO occupation matches the
       original job title and seniority level.

    2. Whether the occupation definition is consistent
       with the complete job description.

    3. Whether the recruiter-confirmed requirements
       support the proposed occupation.

    4. Whether the ESCO skill mappings provide relevant
       supporting evidence.

    Unconfirmed requirements should only be treated as
    supplementary information.

    The final decision must be made by the recruiter.
    """
)


decision = st.radio(
    "Choose your review decision:",
    options=[
        "APPROVED",
        "REJECTED"
    ],
    format_func=lambda value: (
        "Approve occupation mapping"
        if value == "APPROVED"
        else "Reject occupation mapping"
    ),
    horizontal=True
)


# ============================================================
# CONFIRMATION BEFORE SAVING
# ============================================================

with st.form("confirm_occupation_review"):

    confirmed = st.checkbox(
        "I have reviewed this ESCO occupation proposal "
        "and confirm my decision."
    )

    submitted = st.form_submit_button(
        "Confirm Review Decision",
        disabled=not confirmed,
        type="primary"
    )


    if submitted:

        result = save_occupation_review(
            selected_mapping_id,
            decision
        )

        if result["status"] == "SUCCESS":

            if decision == "APPROVED":

                st.success(
                    "ESCO occupation mapping approved successfully."
                )

            else:

                st.warning(
                    "ESCO occupation mapping rejected successfully."
                )

            st.rerun()


        elif result["status"] == "NOT_PENDING_OR_NOT_FOUND":

            st.warning(
                "This proposal is no longer pending. "
                "Please refresh the page."
            )

            st.rerun()


        else:

            st.error(
                f"Could not save the review decision: "
                f"{result['status']}"
            )
