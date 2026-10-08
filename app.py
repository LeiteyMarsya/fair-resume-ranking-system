import streamlit as st

from db import init_database


APP_TITLE = "Fair Resume Ranking System"
APP_ICON = "📄"

PAGES = [
    st.Page("pages/1_Create_Job.py", title="Create Job", icon=":material/work:"),
    st.Page("pages/2_Manage_Jobs.py", title="Manage Jobs", icon=":material/dashboard:"),
    st.Page("pages/3_Upload_Resumes.py", title="Upload Resumes", icon=":material/upload_file:"),
    st.Page("pages/4_Analyze_Job.py", title="Analyze Job", icon=":material/analytics:"),
    st.Page("pages/5_Analyze_Resumes.py", title="Analyze Resumes", icon=":material/search:"),
]


def main() -> None:
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon=APP_ICON,
        layout="wide",
    )

    init_database()

    navigation = st.navigation(PAGES)
    navigation.run()


if __name__ == "__main__":
    main()