
import db

db.init_database()

print("===== ASSESSMENT DETAILS TEST =====")

applications = db.get_application_assessment_details()

print("Total applications:", len(applications))

if applications:

    application = applications[0]

    print("\n===== SAMPLE APPLICATION =====")

    print("Application ID:", application["application_id"])
    print("Blind ID:", application["blind_id"])
    print("Job Title:", application["job_title"])
    print("Resume Filename:", application["original_filename"])
    print("Extraction Status:", application["extraction_status"])
    print("Job Status:", application["job_status"])
    print(
        "Requirements Confirmed:",
        application["requirements_confirmed"]
    )

    # Test retrieving one application.
    application_id = application["application_id"]

    single_application = db.get_application_assessment_details(
        application_id
    )

    assert single_application is not None
    assert single_application["application_id"] == application_id

    print("\nSingle application retrieval: PASSED")

    # Test job requirement retrieval.
    requirements = db.get_job_requirements(
        application["job_id"]
    )

    print("Job requirements found:", len(requirements))

    print("\nApplication details retrieval: PASSED")

else:

    print("No applications found in the database.")

print("\nASSESSMENT DETAILS TEST COMPLETED!")
