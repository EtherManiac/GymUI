"""Application entry point and native Streamlit navigation."""

import streamlit as st

from workout_app.profile_ui import render_user_selection, request_user_selection
from workout_app.users import user_name


# Page configuration must be the first Streamlit command in the application.
st.set_page_config(
    page_title="Personal Workout Planner",
    page_icon="🏋️",
    layout="centered",
    initial_sidebar_state="auto",
)

# Streamlit adds permalink controls to headings by default. Keep headings as
# plain labels throughout every current and future page in this application.
st.html(
    """
    <style>
    [data-testid="stHeaderActionElements"] {
        display: none !important;
    }
    </style>
    """
)

# Profiles are intentionally lightweight selectors rather than authentication
# or privacy boundaries. Hiding navigation makes selection a hard app gate.
if (
    "active_user_id" not in st.session_state
    or st.session_state.get("user_selection_required", False)
):
    user_selection = st.Page(
        render_user_selection,
        title="Select user",
        icon=":material/person:",
        default=True,
    )
    st.navigation([user_selection], position="hidden").run()
    st.stop()

active_user_id = str(st.session_state.active_user_id)
st.sidebar.caption(f"Current user: **{user_name(active_user_id)}**")
st.sidebar.button(
    "Switch user",
    icon=":material/switch_account:",
    width="stretch",
    on_click=request_user_selection,
)
if st.session_state.get("user_selection_required", False):
    st.rerun()

# st.navigation provides a native collapsible sidebar and keeps routing logic small.
navigation = st.navigation(
    [
        st.Page("pages/workout.py", title="Workout", icon="🏋️", default=True),
        st.Page("pages/edit_exercises.py", title="Edit exercises", icon="📝"),
        st.Page("pages/edit_routines.py", title="Edit routines", icon="🧩"),
    ]
)
navigation.run()
