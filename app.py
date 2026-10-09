
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

    st.Page(
        "pages/4_Analyze_Job.py",
        title="Analyze Job",
        icon=":material/analytics:"
    ),

    st.Page(
        "pages/5_Analyze_Resumes.py",
        title="Analyze Resumes",
        icon=":material/document_scanner:"
    ),

    st.Page(
        "pages/6_Bootstrap_Annotations.py",
        title="Bootstrap Annotations",
        icon=":material/rule:"
    ),

    st.Page(
        "pages/7_Review_Annotations.py",
        title="Review Annotations",
        icon=":material/edit_note:"
    ),
]


# ============================================================
# RUN APPLICATION
# ============================================================

pg = st.navigation(pages)

pg.run()