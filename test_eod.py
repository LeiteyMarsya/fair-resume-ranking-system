
import db
import fairness

db.init_database()

print("===== EOD FUNCTION TEST =====")

# We will reuse the four existing dashboard demo applications.
test_application_ids = [1, 2, 3, 4]

# Check that no existing qualification labels will be overwritten.
existing_labels = db.get_qualification_labels(
    include_simulated=True
)

if any(
    record["application_id"] in test_application_ids
    for record in existing_labels
):
    raise RuntimeError(
        "Test stopped: Existing qualification labels found "
        "for applications 1-4. No records were changed."
    )

# Retrieve existing simulated demographic and screening data.
audit_records = db.get_fairness_audit_data(
    include_simulated=True
)

outcome_records = db.get_screening_outcomes(
    include_simulated=True
)

audit_by_id = {
    record["application_id"]: record
    for record in audit_records
    if record["application_id"] in test_application_ids
    and record["availability_status"] == "AVAILABLE"
}

outcomes_by_id = {
    record["application_id"]: record
    for record in outcome_records
    if record["application_id"] in test_application_ids
}

if len(audit_by_id) != 4 or len(outcomes_by_id) != 4:
    raise RuntimeError(
        "Test stopped: Expected dashboard demo data for "
        "applications 1-4 was not found."
    )

# Identify the demographic attribute used by the demo records.
attribute_name = audit_by_id[1]["attribute_name"]

groups = {
    record["attribute_value"].strip().lower()
    for record in audit_by_id.values()
}

if groups != {"female", "male"}:
    raise RuntimeError(
        f"Unexpected demographic groups: {groups}"
    )

# Verify the existing demo selection rates.
female_selected = sum(
    outcomes_by_id[app_id]["favourable_outcome"]
    for app_id in test_application_ids
    if audit_by_id[app_id]["attribute_value"].strip().lower() == "female"
)

male_selected = sum(
    outcomes_by_id[app_id]["favourable_outcome"]
    for app_id in test_application_ids
    if audit_by_id[app_id]["attribute_value"].strip().lower() == "male"
)

if female_selected != 1 or male_selected != 2:
    raise RuntimeError(
        "Unexpected demo outcomes. Expected Female 1/2 "
        "and Male 2/2."
    )

# Add independently assessed simulated qualification labels.
# Female: both qualified.
# Male: both qualified.
qualification_data = {
    1: True,
    2: True,
    3: True,
    4: True
}

for application_id, is_qualified in qualification_data.items():
    db.save_qualification_label(
        application_id=application_id,
        is_qualified=is_qualified,
        is_simulated=True,
        qualification_source="SIMULATED_EOD_TEST_DATA"
    )

try:
    # Calculate EOD using Male as the reference group.
    result = fairness.calculate_eod(
        attribute_name=attribute_name,
        reference_group="Male",
        include_simulated=True
    )

    print("\n===== EOD RESULTS =====")

    for group in result["results"]:
        print(group)

    # Verify expected results.
    results = {
        group["group"].lower(): group
        for group in result["results"]
    }

    assert abs(results["female"]["tpr"] - 0.50) < 0.000001
    assert abs(results["male"]["tpr"] - 1.00) < 0.000001
    assert abs(results["female"]["eod"] - (-0.50)) < 0.000001
    assert abs(results["male"]["eod"]) < 0.000001

    print("\nTPR calculation: PASSED")
    print("EOD calculation: PASSED")

finally:
    # Remove only the qualification labels created by this test.
    connection = db.get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            DELETE FROM fairness_qualification_labels
            WHERE qualification_source = 'SIMULATED_EOD_TEST_DATA'
        """)

        connection.commit()

    finally:
        connection.close()

    print("Test qualification records cleaned up.")

print("\nALL EOD TESTS PASSED!")
