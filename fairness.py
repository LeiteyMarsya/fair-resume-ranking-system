
from __future__ import annotations

from typing import Any
import db


# ============================================================
# PART 6 - FAIRNESS EVALUATION
# ============================================================


def calculate_selection_rates(
    attribute_name: str,
    include_simulated: bool = False,
) -> dict[str, Any]:
    """
    Calculate the selection rate for each demographic group.

    Formula:
        Selection Rate = Selected Applications / Total
                         Applications in Group

    Only applications with both:
        1. Available demographic information
        2. A recorded screening outcome

    are included.

    By default, simulated records are excluded.
    """

    if not isinstance(attribute_name, str) or not attribute_name.strip():
        raise ValueError("Attribute name cannot be empty.")

    if not isinstance(include_simulated, bool):
        raise ValueError("include_simulated must be True or False.")

    attribute_name = attribute_name.strip()

    # --------------------------------------------------------
    # STEP 1: Retrieve demographic audit records
    # --------------------------------------------------------

    audit_records = db.get_fairness_audit_data(
        include_simulated=include_simulated
    )

    # --------------------------------------------------------
    # STEP 2: Retrieve screening outcomes
    # --------------------------------------------------------

    outcome_records = db.get_screening_outcomes(
        include_simulated=include_simulated
    )

    # Create an application ID lookup for screening outcomes.
    outcomes_by_application = {
        record["application_id"]: record["favourable_outcome"]
        for record in outcome_records
    }

    # --------------------------------------------------------
    # STEP 3: Match demographic data with outcomes
    # --------------------------------------------------------

    group_counts = {}

    processed_applications = set()

    for record in audit_records:

        # Match the requested demographic attribute.
        if record["attribute_name"].strip().casefold() != attribute_name.casefold():
            continue

        # Only use available demographic information.
        if record["availability_status"] != "AVAILABLE":
            continue

        demographic_value = record["attribute_value"]

        if demographic_value is None or not demographic_value.strip():
            continue

        application_id = record["application_id"]

        # An application must have a screening outcome.
        if application_id not in outcomes_by_application:
            continue

        # Prevent one application from being counted twice.
        if application_id in processed_applications:
            raise ValueError(
                f"Duplicate demographic records found for "
                f"application {application_id} and attribute "
                f"{attribute_name}."
            )

        processed_applications.add(application_id)

        group_name = demographic_value.strip()

        if group_name not in group_counts:

            group_counts[group_name] = {
                "selected": 0,
                "total": 0,
            }

        outcome = outcomes_by_application[application_id]

        group_counts[group_name]["total"] += 1

        if outcome == 1:
            group_counts[group_name]["selected"] += 1

    # --------------------------------------------------------
    # STEP 4: Calculate selection rate for each group
    # --------------------------------------------------------

    results = []

    for group_name in sorted(group_counts):

        selected = group_counts[group_name]["selected"]

        total = group_counts[group_name]["total"]

        selection_rate = selected / total

        results.append({
            "group": group_name,
            "selected": selected,
            "total": total,
            "selection_rate": selection_rate,
            "selection_rate_percent": selection_rate * 100,
        })

    # --------------------------------------------------------
    # STEP 5: Return structured results
    # --------------------------------------------------------

    return {
        "attribute_name": attribute_name,
        "include_simulated": include_simulated,
        "applications_evaluated": len(processed_applications),
        "groups": results,
    }


def calculate_spd(
    attribute_name: str,
    reference_group: str,
    include_simulated: bool = False,
) -> dict:
    """
    Calculate Statistical Parity Difference (SPD)
    for each demographic group against a reference group.
    """

    selection_data = calculate_selection_rates(
        attribute_name,
        include_simulated
    )

    groups = selection_data["groups"]

    reference = next(
        (
            group for group in groups
            if group["group"].casefold() == reference_group.strip().casefold()
        ),
        None
    )

    if reference is None:
        raise ValueError(
            f"Reference group '{reference_group}' was not found."
        )

    reference_rate = reference["selection_rate"]

    results = []

    for group in groups:
        if group["group"] == reference["group"]:
            continue

        spd = group["selection_rate"] - reference_rate

        results.append({
            "group": group["group"],
            "reference_group": reference["group"],
            "selection_rate": group["selection_rate"],
            "reference_selection_rate": reference_rate,
            "spd": spd,
        })

    return {
        "attribute_name": attribute_name,
        "reference_group": reference["group"],
        "applications_evaluated": selection_data[
            "applications_evaluated"
        ],
        "include_simulated": include_simulated,
        "results": results,
    }


def calculate_dir(
    attribute_name: str,
    reference_group: str,
    include_simulated: bool = False,
) -> dict:
    """
    Calculate Disparate Impact Ratio (DIR)
    for each demographic group against a reference group.
    """

    selection_data = calculate_selection_rates(
        attribute_name,
        include_simulated
    )

    groups = selection_data["groups"]

    reference = next(
        (
            group for group in groups
            if group["group"].casefold() == reference_group.strip().casefold()
        ),
        None
    )

    if reference is None:
        raise ValueError(
            f"Reference group '{reference_group}' was not found."
        )

    reference_rate = reference["selection_rate"]

    results = []

    for group in groups:
        if group["group"] == reference["group"]:
            continue

        if reference_rate == 0:
            dir_value = None
        else:
            dir_value = group["selection_rate"] / reference_rate

        results.append({
            "group": group["group"],
            "reference_group": reference["group"],
            "selection_rate": group["selection_rate"],
            "reference_selection_rate": reference_rate,
            "dir": dir_value,
            "meets_80_percent_rule": (
                dir_value >= 0.80 if dir_value is not None else None
            ),
        })

    return {
        "attribute_name": attribute_name,
        "reference_group": reference["group"],
        "applications_evaluated": selection_data[
            "applications_evaluated"
        ],
        "include_simulated": include_simulated,
        "results": results,
    }


def calculate_eod(
    attribute_name: str,
    reference_group: str,
    include_simulated: bool = False
):
    """
    Calculate Equal Opportunity Difference (EOD).

    EOD = TPR(group) - TPR(reference group)

    TPR = Qualified candidates with favourable outcomes
          / All qualified candidates

    Qualification labels must be independently assessed.
    """

    if not isinstance(attribute_name, str) or not attribute_name.strip():
        raise ValueError("attribute_name must not be empty.")

    if not isinstance(reference_group, str) or not reference_group.strip():
        raise ValueError("reference_group must not be empty.")

    if not isinstance(include_simulated, bool):
        raise ValueError("include_simulated must be True or False.")

    # Retrieve the three required datasets.
    audit_records = db.get_fairness_audit_data(
        include_simulated=include_simulated
    )

    outcome_records = db.get_screening_outcomes(
        include_simulated=include_simulated
    )

    qualification_records = db.get_qualification_labels(
        include_simulated=include_simulated
    )

    # Create lookup dictionaries using application_id.
    outcomes = {
        record["application_id"]: record
        for record in outcome_records
    }

    qualifications = {
        record["application_id"]: record
        for record in qualification_records
    }

    # Store qualification statistics for each demographic group.
    group_statistics = {}

    for audit in audit_records:

        # Match the requested demographic attribute.
        if audit["attribute_name"].lower() != attribute_name.lower():
            continue

        # Only use available demographic information.
        if audit["availability_status"] != "AVAILABLE":
            continue

        group_name = audit["attribute_value"]

        if group_name is None or not str(group_name).strip():
            continue

        application_id = audit["application_id"]

        # Each application must have both an outcome and
        # an independently assessed qualification label.
        if application_id not in outcomes:
            continue

        if application_id not in qualifications:
            continue

        outcome = outcomes[application_id]
        qualification = qualifications[application_id]

        # Only qualified candidates contribute to TPR.
        if qualification["is_qualified"] != 1:
            continue

        if group_name not in group_statistics:
            group_statistics[group_name] = {
                "qualified_total": 0,
                "selected_qualified": 0
            }

        group_statistics[group_name]["qualified_total"] += 1

        if outcome["favourable_outcome"] == 1:
            group_statistics[group_name]["selected_qualified"] += 1

    # Calculate TPR for each group.
    results = []

    reference_tpr = None

    if reference_group in group_statistics:
        reference_data = group_statistics[reference_group]

        if reference_data["qualified_total"] > 0:
            reference_tpr = (
                reference_data["selected_qualified"]
                / reference_data["qualified_total"]
            )

    for group_name, statistics in group_statistics.items():

        qualified_total = statistics["qualified_total"]
        selected_qualified = statistics["selected_qualified"]

        tpr = (
            selected_qualified / qualified_total
            if qualified_total > 0
            else None
        )

        eod = (
            tpr - reference_tpr
            if tpr is not None and reference_tpr is not None
            else None
        )

        results.append({
            "group": group_name,
            "qualified_total": qualified_total,
            "selected_qualified": selected_qualified,
            "tpr": tpr,
            "tpr_percent": tpr * 100 if tpr is not None else None,
            "eod": eod,
            "eod_percent": eod * 100 if eod is not None else None
        })

    return {
        "attribute_name": attribute_name,
        "reference_group": reference_group,
        "reference_tpr": reference_tpr,
        "results": results
    }
