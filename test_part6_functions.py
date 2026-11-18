
import db

print("===== PART 6 FUNCTION TESTING =====")

db.init_database()

connection = db.get_connection()

try:
    cursor = connection.cursor()

    # Confirm test applications exist
    cursor.execute("""
        SELECT application_id
        FROM applications
        WHERE application_id IN (1, 2)
    """)

    existing_ids = {
        row["application_id"]
        for row in cursor.fetchall()
    }

    if existing_ids != {1, 2}:
        raise ValueError("Test applications 1 and 2 are unavailable.")

finally:
    connection.close()


try:
    # ==========================================
    # TEST 1: SAVE DEMOGRAPHIC AUDIT DATA
    # ==========================================

    print("\nTEST 1: Save demographic audit data")

    audit_id_1 = db.save_fairness_audit_data(
        application_id=1,
        attribute_name="gender",
        attribute_value="Female",
        availability_status="AVAILABLE",
        data_source="SIMULATED_TEST_DATA"
    )

    audit_id_2 = db.save_fairness_audit_data(
        application_id=2,
        attribute_name="gender",
        attribute_value="Male",
        availability_status="AVAILABLE",
        data_source="SIMULATED_TEST_DATA"
    )

    print("Application 1 audit ID:", audit_id_1)
    print("Application 2 audit ID:", audit_id_2)

    # ==========================================
    # TEST 2: RETRIEVE DEMOGRAPHIC AUDIT DATA
    # ==========================================

    print("\nTEST 2: Retrieve demographic audit data")

    audit_records = db.get_fairness_audit_data()

    for record in audit_records:
        print(dict(record))

    assert len(audit_records) == 2

    # ==========================================
    # TEST 3: TEST DUPLICATE PREVENTION
    # ==========================================

    print("\nTEST 3: Update existing demographic record")

    updated_audit_id = db.save_fairness_audit_data(
        application_id=1,
        attribute_name="gender",
        attribute_value="Other",
        availability_status="AVAILABLE",
        data_source="SIMULATED_TEST_DATA"
    )

    assert updated_audit_id == audit_id_1

    audit_records = db.get_fairness_audit_data()

    assert len(audit_records) == 2

    print("Duplicate prevention: PASSED")
    print("Existing record updated successfully.")

    # ==========================================
    # TEST 4: RECORD SCREENING OUTCOMES
    # ==========================================

    print("\nTEST 4: Record screening outcomes")

    outcome_id_1 = db.record_screening_outcome(
        application_id=1,
        favourable_outcome=1,
        is_simulated=True,
        outcome_source="SIMULATED_TEST_DATA"
    )

    outcome_id_2 = db.record_screening_outcome(
        application_id=2,
        favourable_outcome=0,
        is_simulated=True,
        outcome_source="SIMULATED_TEST_DATA"
    )

    print("Application 1 outcome ID:", outcome_id_1)
    print("Application 2 outcome ID:", outcome_id_2)

    # ==========================================
    # TEST 5: RETRIEVE SCREENING OUTCOMES
    # ==========================================

    print("\nTEST 5: Retrieve screening outcomes")

    actual_records = db.get_screening_outcomes()

    simulated_records = db.get_screening_outcomes(
        include_simulated=True
    )

    print("Actual records:", len(actual_records))
    print("All records:", len(simulated_records))

    assert len(actual_records) == 0
    assert len(simulated_records) == 2

    for record in simulated_records:
        print(dict(record))

    print("Simulated data filtering: PASSED")

    # ==========================================
    # TEST 6: UPDATE EXISTING SCREENING OUTCOME
    # ==========================================

    print("\nTEST 6: Update existing screening outcome")

    updated_outcome_id = db.record_screening_outcome(
        application_id=1,
        favourable_outcome=0,
        is_simulated=True,
        outcome_source="SIMULATED_TEST_DATA"
    )

    assert updated_outcome_id == outcome_id_1

    simulated_records = db.get_screening_outcomes(
        include_simulated=True
    )

    assert len(simulated_records) == 2

    print("Duplicate prevention: PASSED")
    print("Existing outcome updated successfully.")

    print("\nALL PART 6 TESTS PASSED!")

finally:
    # Remove only the test records created by this script.
    connection = db.get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            DELETE FROM fairness_audit_data
            WHERE data_source = 'SIMULATED_TEST_DATA'
        """)

        cursor.execute("""
            DELETE FROM fairness_screening_outcomes
            WHERE outcome_source = 'SIMULATED_TEST_DATA'
              AND is_simulated = 1
        """)

        connection.commit()

        print("\nTest records cleaned up successfully.")

    finally:
        connection.close()

print("\n===== TESTING COMPLETED =====")
