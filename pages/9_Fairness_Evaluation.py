
import streamlit as st
import pandas as pd

import db
import fairness


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.title("Fairness Evaluation Dashboard")

st.write(
    "Evaluate whether the resume screening process produces "
    "different selection outcomes across demographic groups."
)

st.divider()


# ============================================================
# DATA SETTINGS
# ============================================================

include_simulated = st.checkbox(
    "Include simulated test data",
    value=False,
    help="Enable this only when testing the fairness metrics."
)

audit_records = db.get_fairness_audit_data(
    include_simulated=include_simulated
)

# Identify demographic attributes with available values.
available_attributes = sorted({
    record["attribute_name"]
    for record in audit_records
    if record["availability_status"] == "AVAILABLE"
    and record["attribute_value"]
    and record["attribute_value"].strip()
})


# ============================================================
# EMPTY STATE
# ============================================================

if not available_attributes:

    st.info(
        "No demographic audit data is currently available. "
        "Add demographic audit records before evaluating fairness."
    )

    st.caption(
        "Demographic attributes are used exclusively for fairness "
        "evaluation, not candidate screening."
    )

    st.stop()


# ============================================================
# ATTRIBUTE SELECTION
# ============================================================

st.subheader("Evaluation Settings")

selected_attribute = st.selectbox(
    "Select demographic attribute",
    available_attributes
)

selection_data = fairness.calculate_selection_rates(
    attribute_name=selected_attribute,
    include_simulated=include_simulated
)

groups = selection_data["groups"]

if not groups:

    st.warning(
        "There are no eligible applications with both "
        "available demographic information and recorded outcomes."
    )

    st.stop()


# ============================================================
# REFERENCE GROUP
# ============================================================

group_names = [group["group"] for group in groups]

reference_group = st.selectbox(
    "Select reference group",
    group_names
)


# ============================================================
# 1. SELECTION RATE
# ============================================================

st.divider()
st.subheader("1. Selection Rate")

st.caption(
    "Percentage of applications receiving favourable screening outcomes."
)

selection_table = []

for group in groups:

    selection_table.append({
        "Demographic Group": group["group"],
        "Selected": group["selected"],
        "Total Applications": group["total"],
        "Selection Rate (%)": round(
            group["selection_rate_percent"], 2
        )
    })

st.dataframe(
    pd.DataFrame(selection_table),
    use_container_width=True,
    hide_index=True
)


# ============================================================
# 2. STATISTICAL PARITY DIFFERENCE (SPD)
# ============================================================

st.divider()
st.subheader("2. Statistical Parity Difference (SPD)")

spd_data = fairness.calculate_spd(
    attribute_name=selected_attribute,
    reference_group=reference_group,
    include_simulated=include_simulated
)

if spd_data["results"]:

    spd_table = []

    for result in spd_data["results"]:

        spd_table.append({
            "Group": result["group"],
            "Reference Group": result["reference_group"],
            "SPD": round(result["spd"], 4)
        })

    st.dataframe(
        pd.DataFrame(spd_table),
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        "SPD = Selection Rate of Group - Selection Rate of Reference Group."
    )

else:

    st.info(
        "Only one demographic group is available. "
        "Another group is required for comparison."
    )


# ============================================================
# 3. DISPARATE IMPACT RATIO (DIR)
# ============================================================

st.divider()
st.subheader("3. Disparate Impact Ratio (DIR)")

dir_data = fairness.calculate_dir(
    attribute_name=selected_attribute,
    reference_group=reference_group,
    include_simulated=include_simulated
)

if dir_data["results"]:

    dir_table = []

    for result in dir_data["results"]:

        dir_value = result["dir"]

        dir_table.append({
            "Group": result["group"],
            "Reference Group": result["reference_group"],
            "DIR": (
                round(dir_value, 4)
                if dir_value is not None
                else "Undefined"
            ),
            "80% Rule": (
                "Meets guideline"
                if result["meets_80_percent_rule"] is True
                else "Below guideline"
                if result["meets_80_percent_rule"] is False
                else "Cannot evaluate"
            )
        })

    st.dataframe(
        pd.DataFrame(dir_table),
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        "DIR = Selection Rate of Group / Selection Rate of Reference Group."
    )

    st.caption(
        "A DIR below 0.80 is a screening indicator for further "
        "investigation, not proof of discrimination."
    )

else:

    st.info(
        "Only one demographic group is available. "
        "Another group is required for comparison."
    )


# ============================================================
# 4. EQUAL OPPORTUNITY DIFFERENCE (EOD)
# ============================================================

st.divider()
st.subheader("4. Equal Opportunity Difference (EOD)")

st.caption(
    "Measures the difference in True Positive Rate (TPR) "
    "between demographic groups."
)

eod_data = fairness.calculate_eod(
    attribute_name=selected_attribute,
    reference_group=reference_group,
    include_simulated=include_simulated
)

if eod_data["results"]:

    eod_table = []

    for result in eod_data["results"]:

        eod_table.append({
            "Group": result["group"],
            "Qualified Candidates": result["qualified_total"],
            "Selected Qualified": result["selected_qualified"],
            "TPR (%)": (
                round(result["tpr_percent"], 2)
                if result["tpr_percent"] is not None
                else "Undefined"
            ),
            "EOD": (
                round(result["eod"], 4)
                if result["eod"] is not None
                else "Undefined"
            )
        })

    st.dataframe(
        pd.DataFrame(eod_table),
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        "TPR = Selected Qualified Candidates / All Qualified Candidates."
    )

    st.caption(
        "EOD = TPR of Group - TPR of Reference Group."
    )

    st.caption(
        "An EOD of 0 indicates equal TPR. A negative value indicates "
        "a lower TPR than the reference group, while a positive value "
        "indicates a higher TPR."
    )

    if eod_data["reference_tpr"] is None:

        st.warning(
            "EOD cannot be fully evaluated because the reference group "
            "has no independently assessed qualified candidates."
        )

else:

    st.info(
        "No eligible qualification labels are currently available "
        "for this demographic attribute. Add independently assessed "
        "qualification labels before evaluating EOD."
    )


# ============================================================
# EVALUATION SUMMARY
# ============================================================

st.divider()
st.subheader("Evaluation Summary")

col1, col2 = st.columns(2)

col1.metric(
    "Applications Evaluated",
    selection_data["applications_evaluated"]
)

col2.metric(
    "Demographic Groups",
    len(groups)
)

st.caption(
    "This dashboard evaluates screening outcomes. "
    "Demographic information must not influence candidate ranking "
    "or selection decisions."
)

st.info(
    "EOD relies on independently assessed qualification labels. "
    "These labels must represent actual candidate qualifications "
    "and must not be inferred from screening outcomes."
)
