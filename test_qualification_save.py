
import db

db.init_database()

application_id = int(input("Enter Application ID: "))

connection = db.get_connection()

try:
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            application_id,
            is_qualified,
            is_simulated,
            qualification_source,
            recorded_at
        FROM fairness_qualification_labels
        WHERE application_id = ?
        """,
        (application_id,)
    )

    record = cursor.fetchone()

    if record is None:
        print("FAIL: No qualification label found.")

    else:
        print("\n===== QUALIFICATION LABEL =====")
        print("Application ID:", record["application_id"])
        print("Decision:", "Qualified" if record["is_qualified"] == 1 else "Not Qualified")
        print("Simulated:", record["is_simulated"])
        print("Source:", record["qualification_source"])
        print("Recorded At:", record["recorded_at"])

        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM fairness_qualification_labels
            WHERE application_id = ?
            """,
            (application_id,)
        )

        count = cursor.fetchone()["total"]

        print("\nRecords for this application:", count)

        if count == 1 and record["is_simulated"] == 0:
            print("TEST PASSED")
        else:
            print("TEST FAILED")

finally:
    connection.close()
