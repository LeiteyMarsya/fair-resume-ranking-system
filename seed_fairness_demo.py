
import db

db.init_database()

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

for application_id, gender in demographics:
    db.save_fairness_audit_data(
        application_id=application_id,
        attribute_name="gender",
        attribute_value=gender,
        availability_status="AVAILABLE",
        data_source="SIMULATED_DASHBOARD_DEMO",
        is_simulated=True
    )

for application_id, outcome in outcomes:
    db.record_screening_outcome(
        application_id=application_id,
        favourable_outcome=outcome,
        is_simulated=True,
        outcome_source="SIMULATED_DASHBOARD_DEMO"
    )

print("Dashboard demonstration data inserted successfully.")
