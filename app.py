"""Application entry point and native Streamlit navigation."""

import streamlit as st


# Page configuration must be the first Streamlit command in the application.
st.set_page_config(
    page_title="Personal Workout Planner",
    page_icon="🏋️",
    layout="centered",
    initial_sidebar_state="auto",
)

# st.navigation provides a native collapsible sidebar and keeps routing logic small.
navigation = st.navigation(
    [
        st.Page("pages/workout.py", title="Workout", icon="🏋️", default=True),
        st.Page("pages/edit_exercises.py", title="Edit exercises", icon="📝"),
        st.Page("pages/edit_routines.py", title="Edit routines", icon="🧩"),
    ]
)
navigation.run()

