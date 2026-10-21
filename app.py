"""Application entry point and native Streamlit navigation."""

import streamlit as st

from workout_app.calendar_logic import local_today, scheduled_event_on_date
from workout_app.profile_ui import render_user_selection, request_user_selection
from workout_app.storage import DataLoadError, load_calendar, load_workout_draft
from workout_app.ui_helpers import load_data_or_stop
from workout_app.users import user_name
from workout_app.validation import DataValidationError


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

# Register every page before shared controls so today's scheduled workout can
# route to the Workout page even when the user last visited an editor page.
workout_page = st.Page(
    "pages/workout.py", title="Workout", icon="🏋️", default=True
)
navigation = st.navigation(
    [
        workout_page,
        st.Page("pages/calendar.py", title="Calendar", icon=":material/calendar_month:"),
        st.Page("pages/edit_exercises.py", title="Edit exercises", icon="📝"),
        st.Page("pages/edit_routines.py", title="Edit routines", icon="🧩"),
    ]
)

st.sidebar.caption(f"Current user: **{user_name(active_user_id)}**")
st.sidebar.button(
    "Switch user",
    icon=":material/switch_account:",
    width="stretch",
    on_click=request_user_selection,
)
if st.session_state.get("user_selection_required", False):
    st.rerun()

# Resolve today's explicit schedule once per profile/day. A recoverable draft
# keeps priority so opening the app never silently discards workout progress.
exercise_document, routine_document = load_data_or_stop(active_user_id)
today = local_today()
schedule_marker = f"{active_user_id}:{today.isoformat()}"
try:
    calendar_document = load_calendar(active_user_id)
except (DataLoadError, DataValidationError):
    calendar_document = None

if st.session_state.get("calendar_schedule_checked") != schedule_marker:
    st.session_state.calendar_schedule_checked = schedule_marker
    scheduled_event = (
        scheduled_event_on_date(calendar_document, today)
        if calendar_document is not None
        else None
    )
    routine_ids = {routine["id"] for routine in routine_document["routines"]}
    if scheduled_event and scheduled_event["routine_id"] in routine_ids:
        st.session_state.todays_scheduled_routine_id = scheduled_event["routine_id"]
        st.session_state.calendar_scheduled_event_id = scheduled_event["id"]
        if load_workout_draft(active_user_id, routine_document) is None:
            st.session_state.workout_routine_id = scheduled_event["routine_id"]
            st.session_state.pop("active_workout_identity", None)
        st.session_state.open_scheduled_workout_requested = True
    else:
        st.session_state.pop("todays_scheduled_routine_id", None)
        st.session_state.pop("calendar_scheduled_event_id", None)

if st.session_state.pop("open_scheduled_workout_requested", False):
    st.switch_page(workout_page)
navigation.run()
