"""Shared Streamlit profile-selection gate."""

from __future__ import annotations

import streamlit as st

from workout_app.users import USER_NAMES


def request_user_selection() -> None:
    """Ask the next script pass to clear state and show only user choices."""

    st.session_state.user_selection_required = True


def render_user_selection() -> None:
    """Render a hard gate with no sidebar or page navigation."""

    if st.session_state.get("user_selection_required", False):
        st.session_state.clear()
    st.html(
        """
        <style>
        section[data-testid="stSidebar"],
        [data-testid="stSidebarCollapsedControl"] {
            display: none !important;
        }
        </style>
        """
    )
    st.title("Personal Workout Planner")
    st.subheader("Who is working out?")
    user_columns = st.columns(len(USER_NAMES))
    for column, (user_id, display_name) in zip(user_columns, USER_NAMES.items()):
        if column.button(
            display_name,
            key=f"select_user_{user_id}",
            icon=":material/person:",
            width="stretch",
        ):
            st.session_state.clear()
            st.session_state.active_user_id = user_id
            st.rerun()


def require_active_user() -> str:
    """Stop the current page behind the selector until a user is chosen."""

    if (
        "active_user_id" not in st.session_state
        or st.session_state.get("user_selection_required", False)
    ):
        render_user_selection()
        st.stop()
    return str(st.session_state.active_user_id)

