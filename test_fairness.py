
import db
import fairness


print("===== SELECTION RATE TESTING =====")

db.init_database()

test_application_ids = {1, 2, 3, 4}

# Ensure the test will not overwrite existing fairness records.
existing_audits = db.get_fairness_audit_data(
    include_simulated=True
)

existing_outcomes = db.get_screening_outcomes(
    include_simulated=True
)

if any(
    row["application_id"] in test_application_ids
    and row["attribute_name"].casefold() == "gender"
    for row in existing_audits
):
    raise RuntimeError("Test demographic records already exist.")

if any(
    row["application_id"] in test_application_ids
    for row in existing_outcomes
):
    raise RuntimeError("Test screening outcomes already exist.")


try:

    # ==========================================
    # TEST DATA - SIMULATED ONLY
    # ==========================================

    print("\nTEST 1: Insert simulated demographic data")

    test_demographics = [
        (1, "Female"),
        (2, "Female"),
        (3, "Male"),
        (4, "Male"),
    ]

    for application_id, gender in test_demographics:

        db.save_fairness_audit_data(
            application_id=application_id,
            attribute_name="gender",
            attribute_value=gender,
            availability_status="AVAILABLE",
            data_source="SIMULATED_TEST_DATA",
            is_simulated=True,
        )

    print("4 demographic records inserted.")

    # ==========================================
    # TEST 2: INSERT SCREENING OUTCOMES
    # ==========================================

    print("\nTEST 2: Insert simulated screening outcomes")

    test_outcomes = [
        (1, 1),
        (2, 0),
        (3, 1),
        (4, 1),
    ]

    for application_id, outcome in test_outcomes:

        db.record_screening_outcome(
            application_id=application_id,
            favourable_outcome=outcome,
            is_simulated=True,
            outcome_source="SIMULATED_TEST_DATA",
        )

    print("4 screening outcomes inserted.")

    # ==========================================
    # TEST 3: ACTUAL DATA FILTERING
    # ==========================================

    print("\nTEST 3: Calculate using actual records only")

    actual_results = fairness.calculate_selection_rates(
        attribute_name="gender"
    )

    print("Applications evaluated:",
          actual_results["applications_evaluated"])

    assert actual_results["applications_evaluated"] == 0
    assert actual_results["groups"] == []

    print("Actual data filtering: PASSED")

    # ==========================================
    # TEST 4: SIMULATED SELECTION RATE
    # ==========================================

    print("\nTEST 4: Calculate simulated selection rates")

    results = fairness.calculate_selection_rates(
        attribute_name="gender",
        include_simulated=True,
    )

    print("Applications evaluated:",
          results["applications_evaluated"])

    for group in results["groups"]:

        print(
            f"{group['group']}: "
            f"{group['selected']}/{group['total']} "
            f"= {group['selection_rate_percent']:.2f}%"
        )

    # Expected:
    # Female: 1/2 = 50%
    # Male:   2/2 = 100%

    expected_rates = {
        "Female": 50.0,
        "Male": 100.0,
    }

    assert results["applications_evaluated"] == 4

    for group in results["groups"]:

        expected = expected_rates[group["group"]]

        assert group["selection_rate_percent"] == expected

    print("Selection Rate calculation: PASSED")

    print("\nALL SELECTION RATE TESTS PASSED!")

finally:

    # ==========================================
    # CLEAN UP SIMULATED TEST RECORDS
    # ==========================================

    connection = db.get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute("""
            DELETE FROM fairness_audit_data
            WHERE application_id IN (1, 2, 3, 4)
              AND data_source = 'SIMULATED_TEST_DATA'
              AND is_simulated = 1
        """)

        cursor.execute("""
            DELETE FROM fairness_screening_outcomes
            WHERE application_id IN (1, 2, 3, 4)
              AND outcome_source = 'SIMULATED_TEST_DATA'
              AND is_simulated = 1
        """)

        connection.commit()

        print("\nSimulated test records cleaned up.")

    finally:

        connection.close()

print("\n===== TESTING COMPLETED =====")
