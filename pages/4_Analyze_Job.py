import streamlit as st

from db import (
    get_all_jobs,
    get_job,
    delete_job_requirements,
    create_job_requirement,
    get_job_requirements,
    confirm_job_requirements,
)

from job_analyzer import (
    analyze_job_description
)


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.title(
    "Analyze Job Requirements"
)

st.caption(
    "Automatically extract job requirements "
    "and allow the recruiter to verify them."
)


# ============================================================
# LOAD JOBS
# ============================================================

jobs = get_all_jobs()


if not jobs:

    st.info(
        "No jobs available. "
        "Create a job first."
    )

    st.stop()


# ============================================================
# JOB SELECTION
# ============================================================

job_options = {
    (
        f"#{job['job_id']} — "
        f"{job['job_title']} "
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


job = get_job(
    selected_job_id
)


# ============================================================
# JOB INFORMATION
# ============================================================

st.divider()

st.subheader(
    job["job_title"]
)

st.write(
    f"**Job Level:** "
    f"{job['seniority_level']}"
)

st.write(
    f"**Status:** "
    f"{job['status']}"
)


# ============================================================
# JOB DESCRIPTION
# ============================================================

with st.expander(
    "View Job Description"
):

    st.text_area(
        "Description",
        job["description"],
        height=350,
        disabled=True
    )


# ============================================================
# ANALYZE JOB
# ============================================================

st.divider()

st.subheader(
    "1. Automatic Analysis"
)


st.warning(
    "The extracted requirements are only predictions. "
    "The recruiter must review and confirm them before "
    "the job can become ACTIVE."
)


if st.button(
    "Analyze Job Description",
    type="primary"
):

    analysis = analyze_job_description(
        job["description"]
    )

    requirements = analysis[
        "requirements"
    ]

    # --------------------------------------------------------
    # Replace previous analysis
    # --------------------------------------------------------

    delete_job_requirements(
        selected_job_id
    )

    # --------------------------------------------------------
    # Save new requirements
    # --------------------------------------------------------

    for requirement in requirements:

        create_job_requirement(
            job_id=selected_job_id,

            requirement_text=(
                requirement[
                    "requirement_text"
                ]
            ),

            category=(
                requirement[
                    "category"
                ]
            ),

            requirement_type=(
                requirement[
                    "requirement_type"
                ]
            ),

            importance_weight=(
                requirement[
                    "importance_weight"
                ]
            ),

            mandatory=(
                requirement[
                    "mandatory"
                ]
            ),

            confidence=(
                requirement[
                    "confidence"
                ]
            ),

            source=(
                requirement[
                    "source"
                ]
            ),

            recruiter_verified=False,
        )


    st.success(
        f"{len(requirements)} "
        "requirement(s) extracted."
    )

    st.rerun()


# ============================================================
# CURRENT REQUIREMENTS
# ============================================================

requirements = get_job_requirements(
    selected_job_id
)


if requirements:

    st.divider()

    st.subheader(
        "2. Recruiter Verification"
    )

    st.write(
        "Review every extracted requirement. "
        "You can change its type, category, importance "
        "or remove it before confirmation."
    )


    edited_requirements = []


    for requirement in requirements:

        with st.container(
            border=True
        ):

            col1, col2 = st.columns(
                [3, 1]
            )


            with col1:

                edited_text = st.text_input(
                    "Requirement",
                    value=(
                        requirement[
                            "requirement_text"
                        ]
                    ),
                    key=(
                        f"text_"
                        f"{requirement['requirement_id']}"
                    )
                )


            with col2:

                category = st.selectbox(
                    "Category",

                    [
                        "SKILL",
                        "EDUCATION",
                        "EXPERIENCE",
                        "CERTIFICATION",
                        "OTHER"
                    ],

                    index=[
                        "SKILL",
                        "EDUCATION",
                        "EXPERIENCE",
                        "CERTIFICATION",
                        "OTHER"
                    ].index(
                        requirement[
                            "category"
                        ]
                    ),

                    key=(
                        f"category_"
                        f"{requirement['requirement_id']}"
                    )
                )


            col3, col4, col5 = st.columns(
                3
            )


            with col3:

                requirement_type = st.selectbox(
                    "Requirement Type",

                    [
                        "REQUIRED",
                        "PREFERRED",
                        "UNSPECIFIED"
                    ],

                    index=[
                        "REQUIRED",
                        "PREFERRED",
                        "UNSPECIFIED"
                    ].index(
                        requirement[
                            "requirement_type"
                        ]
                    ),

                    key=(
                        f"type_"
                        f"{requirement['requirement_id']}"
                    )
                )


            with col4:

                importance = st.number_input(
                    "Importance Weight",

                    min_value=0.0,

                    max_value=5.0,

                    value=float(
                        requirement[
                            "importance_weight"
                        ]
                    ),

                    step=0.5,

                    key=(
                        f"weight_"
                        f"{requirement['requirement_id']}"
                    ),

                    help=(
                        "Higher value means this requirement "
                        "will eventually contribute more to "
                        "the candidate matching score."
                    )
                )


            with col5:

                mandatory = st.checkbox(
                    "Mandatory",

                    value=bool(
                        requirement[
                            "mandatory"
                        ]
                    ),

                    key=(
                        f"mandatory_"
                        f"{requirement['requirement_id']}"
                    )
                )


            st.caption(
                f"AI confidence: "
                f"{requirement['confidence']:.0%}"
            )

            st.caption(
                f"Detection source: "
                f"{requirement['source']}"
            )


            edited_requirements.append(
                {
                    "requirement_id":
                        requirement[
                            "requirement_id"
                        ],

                    "text":
                        edited_text.strip(),

                    "category":
                        category,

                    "requirement_type":
                        requirement_type,

                    "importance":
                        importance,

                    "mandatory":
                        mandatory,
                }
            )


    # ========================================================
    # SAVE / CONFIRM
    # ========================================================

    st.divider()

    st.subheader(
        "3. Confirm Job Profile"
    )


    st.write(
        "Only confirm after checking the extracted "
        "requirements. These requirements will later "
        "be used to evaluate candidate relevance."
    )


    if st.button(
        "Confirm Requirements",
        type="primary"
    ):

        # ----------------------------------------------------
        # Validate
        # ----------------------------------------------------

        invalid = False

        for item in edited_requirements:

            if not item["text"]:

                st.error(
                    "A requirement cannot be empty."
                )

                invalid = True

                break


            if item["importance"] <= 0:

                st.error(
                    f"Importance weight must be greater "
                    f"than 0 for: {item['text']}"
                )

                invalid = True

                break


            # ------------------------------------------------
            # Fairness safeguard:
            #
            # An unspecified requirement is not allowed
            # to become a mandatory hard requirement
            # without recruiter explicitly selecting
            # REQUIRED.
            # ------------------------------------------------

            if (
                item["requirement_type"]
                == "REQUIRED"
            ):

                item["mandatory"] = True


        if invalid:

            st.stop()


        # ----------------------------------------------------
        # Replace old requirements
        # ----------------------------------------------------

        delete_job_requirements(
            selected_job_id
        )


        # ----------------------------------------------------
        # Save recruiter-confirmed requirements
        # ----------------------------------------------------

        for item in edited_requirements:

            create_job_requirement(

                job_id=selected_job_id,

                requirement_text=item["text"],

                category=item["category"],

                requirement_type=(
                    item[
                        "requirement_type"
                    ]
                ),

                importance_weight=(
                    item[
                        "importance"
                    ]
                ),

                mandatory=(
                    item[
                        "mandatory"
                    ]
                ),

                confidence=1.0,

                source="RECRUITER_VERIFIED",

                recruiter_verified=True,
            )


        # ----------------------------------------------------
        # Mark the job as confirmed
        # ----------------------------------------------------

        confirm_job_requirements(
            selected_job_id
        )


        st.success(
            "Job requirements confirmed successfully."
        )

        st.info(
            "The job can now be changed from DRAFT "
            "to ACTIVE."
        )

        st.rerun()


else:

    st.info(
        "No requirements have been extracted yet. "
        "Click 'Analyze Job Description' above."
    )