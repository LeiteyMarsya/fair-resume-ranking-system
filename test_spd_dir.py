
import db
import fairness


print("===== SPD AND DIR TESTING =====")

test_application_ids = [1, 2, 3, 4]

try:
    db.init_database()

    # TEST DATA
    print("\nTEST 1: Insert simulated test data")

    demographics = [
        (1, "Female"),
        (2, "Female"),
        (3, "Male"),
        (4, "Male"),
    ]

    outcomes = [
        (1, 1),
        (2, 0),
        (3, 1),
        (4, 1),
    ]

    connection = db.get_connection()
    cursor = connection.cursor()

    # Prevent accidental replacement of existing data.
    placeholders = ",".join("?" for _ in test_application_ids)

    cursor.execute(
        f"""
        SELECT COUNT(*)
        FROM fairness_audit_data
        WHERE application_id IN ({placeholders})
          AND attribute_name = 'gender'
        """,
        test_application_ids
    )

    if cursor.fetchone()[0] > 0:
        raise RuntimeError("Existing gender audit records found.")

    cursor.execute(
        f"""
        SELECT COUNT(*)
        FROM fairness_screening_outcomes
        WHERE application_id IN ({placeholders})
        """,
        test_application_ids
    )

    if cursor.fetchone()[0] > 0:
        raise RuntimeError("Existing screening outcomes found.")

    connection.close()

    for application_id, gender in demographics:
        db.save_fairness_audit_data(
            application_id=application_id,
            attribute_name="gender",
            attribute_value=gender,
            availability_status="AVAILABLE",
            data_source="SIMULATED_TEST_DATA",
            is_simulated=True
        )

    for application_id, outcome in outcomes:
        db.record_screening_outcome(
            application_id=application_id,
            favourable_outcome=outcome,
            is_simulated=True,
            outcome_source="SIMULATED_TEST_DATA"
        )

    print("4 demographic records inserted.")
    print("4 screening outcomes inserted.")

    # TEST SPD
    print("\nTEST 2: Calculate SPD")

    spd_result = fairness.calculate_spd(
        attribute_name="gender",
        reference_group="Male",
        include_simulated=True
    )

    for result in spd_result["results"]:
        print(
            f'{result["group"]}: '
            f'SPD = {result["spd"]:.2f}'
        )

    female_spd = next(
        item for item in spd_result["results"]
        if item["group"] == "Female"
    )

    assert abs(female_spd["spd"] - (-0.50)) < 0.000001

    print("SPD calculation: PASSED")

    # TEST DIR
    print("\nTEST 3: Calculate DIR")

    dir_result = fairness.calculate_dir(
        attribute_name="gender",
        reference_group="Male",
        include_simulated=True
    )

    for result in dir_result["results"]:
        print(
            f'{result["group"]}: '
            f'DIR = {result["dir"]:.2f}, '
            f'80% rule = {result["meets_80_percent_rule"]}'
        )

    female_dir = next(
        item for item in dir_result["results"]
        if item["group"] == "Female"
    )

    assert abs(female_dir["dir"] - 0.50) < 0.000001
    assert female_dir["meets_80_percent_rule"] is False

    print("DIR calculation: PASSED")

    print("\nALL SPD AND DIR TESTS PASSED!")

finally:
    # CLEAN UP ONLY OUR SIMULATED TEST RECORDS
    connection = db.get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            DELETE FROM fairness_audit_data
            WHERE data_source = 'SIMULATED_TEST_DATA'
              AND is_simulated = 1
              AND attribute_name = 'gender'
        """)

        cursor.execute("""
            DELETE FROM fairness_screening_outcomes
            WHERE outcome_source = 'SIMULATED_TEST_DATA'
              AND is_simulated = 1
        """)

        connection.commit()

        print("\nSimulated test records cleaned up.")

    finally:
        connection.close()
