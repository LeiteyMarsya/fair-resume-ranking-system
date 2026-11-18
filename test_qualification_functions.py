
import db

db.init_database()

print("===== QUALIFICATION FUNCTION TEST =====")

# Check whether application ID 1 already has a qualification label.
existing_records = db.get_qualification_labels(include_simulated=True)

if any(record["application_id"] == 1 for record in existing_records):
    print("Test stopped: Application ID 1 already has a qualification label.")
    print("Please choose another unused application ID before testing.")

else:
    # Test simulated data insertion.
    db.save_qualification_label(
        application_id=1,
        is_qualified=True,
        is_simulated=True,
        qualification_source="SIMULATED_TEST_DATA"
    )

    records = db.get_qualification_labels(include_simulated=True)

    test_record = next(
        record for record in records
        if record["application_id"] == 1
    )

    assert test_record["is_qualified"] == 1
    assert test_record["is_simulated"] == 1

    print("Qualification label insertion: PASSED")

    # Test simulated data filtering.
    actual_records = db.get_qualification_labels()

    assert not any(
        record["application_id"] == 1
        for record in actual_records
    )

    print("Simulated data filtering: PASSED")

    # Clean up test record.
    connection = db.get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            DELETE FROM fairness_qualification_labels
            WHERE application_id = 1
              AND is_simulated = 1
              AND qualification_source = 'SIMULATED_TEST_DATA'
        """)

        connection.commit()

    finally:
        connection.close()

    print("Test records cleaned up.")
    print("\nALL QUALIFICATION FUNCTION TESTS PASSED!")
