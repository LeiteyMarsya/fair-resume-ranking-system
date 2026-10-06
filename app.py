import streamlit as st

from db import init_database


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Fair Resume Ranking System",
    page_icon="📄",
    layout="wide",
)


# ============================================================
# INITIALIZE DATABASE
# ============================================================

init_database()


# ============================================================
# APPLICATION NAVIGATION
# ============================================================

pages = [
    st.Page(
        "pages/1_Create_Job.py",
        title="Create Job",
        icon=":material/work:"
    ),

    st.Page(
        "pages/2_Manage_Jobs.py",
        title="Manage Jobs",
        icon=":material/dashboard:"
    ),

    st.Page(
        "pages/3_Upload_Resumes.py",
        title="Upload Resumes",
        icon=":material/upload_file:"
    ),
]


pg = st.navigation(pages)

pg.run()