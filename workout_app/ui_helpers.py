"""Reusable Streamlit UI helpers shared by all pages."""

from __future__ import annotations

from typing import Any

import streamlit as st

from workout_app.storage import (
    DataLoadError,
    data_bundle_json,
    load_calendar,
    load_data,
    load_split,
    parse_data_bundle,
    save_calendar,
    save_data,
    save_split,
)
from workout_app.validation import DataValidationError


def load_data_or_stop(user_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load application data or stop the page with useful recovery guidance."""

    try:
        return load_data(user_id)
    except (DataLoadError, DataValidationError) as error:
        st.error("The workout data could not be loaded.")
        st.code(str(error))
        st.info("Correct the JSON files or import a valid backup, then reload the page.")
        st.stop()


def show_save_error(error: Exception) -> None:
    """Display validation/storage errors consistently after an edit."""

    st.error("Your changes were not saved.")
    st.code(str(error))


def render_data_portability(
    user_id: str,
    exercise_document: dict[str, Any],
    routine_document: dict[str, Any],
) -> None:
    """Render backup import/export controls in the sidebar.

    Import is deliberately explicit because it replaces all profile data.
    """

    with st.sidebar.expander("Data backup", expanded=False):
        st.caption(
            "Cloud file edits may disappear after a restart. Download a backup after editing."
        )
        try:
            calendar_document = load_calendar(user_id)
            split_document = load_split(user_id, routine_document)
        except (DataLoadError, DataValidationError) as error:
            st.error(
                "The calendar and workout split must be valid before downloading a backup."
            )
            st.code(str(error))
        else:
            st.download_button(
                "Download backup",
                data=data_bundle_json(
                    exercise_document,
                    routine_document,
                    calendar_document,
                    split_document,
                ),
                file_name=f"workout_planner_{user_id}_backup.json",
                mime="application/json",
                width="stretch",
            )
        uploaded_backup = st.file_uploader(
            "Restore a backup", type=["json"], key=f"backup_uploader_{user_id}"
        )
        if st.button(
            "Import and replace data",
            disabled=uploaded_backup is None,
            width="stretch",
        ):
            try:
                (
                    imported_exercises,
                    imported_routines,
                    imported_calendar,
                    imported_split,
                ) = parse_data_bundle(uploaded_backup.getvalue())
                save_data(user_id, imported_exercises, imported_routines)
                save_calendar(user_id, imported_calendar)
                save_split(user_id, imported_split, imported_routines)
            except (DataLoadError, DataValidationError) as error:
                show_save_error(error)
            else:
                st.success("Backup imported.")
                st.rerun()


def normalized_tags(raw_tags: str) -> list[str]:
    """Convert comma-separated tags to a stable, case-insensitive unique list."""

    tags: list[str] = []
    seen: set[str] = set()
    for raw_tag in raw_tags.split(","):
        tag = raw_tag.strip()
        normalized = tag.casefold()
        if tag and normalized not in seen:
            tags.append(tag)
            seen.add(normalized)
    return tags


def all_tags(exercise_document: dict[str, Any]) -> list[str]:
    """Return every exercise tag in a friendly sorted order."""

    return sorted(
        {tag for exercise in exercise_document["exercises"] for tag in exercise["tags"]},
        key=str.casefold,
    )


def all_muscles(exercise_document: dict[str, Any]) -> list[str]:
    """Return every targeted muscle in a friendly sorted order."""

    return sorted(
        {
            muscle
            for exercise in exercise_document["exercises"]
            for muscle in exercise["muscles_targeted"]
        },
        key=str.casefold,
    )


def exercises_matching_filters(
    exercise_document: dict[str, Any],
    required_muscles: list[str],
    required_tags: list[str],
) -> list[dict[str, Any]]:
    """Filter exercises using match-all semantics for muscles and tags."""

    muscles = {muscle.casefold() for muscle in required_muscles}
    tags = {tag.casefold() for tag in required_tags}
    return [
        exercise
        for exercise in exercise_document["exercises"]
        if muscles.issubset(
            {muscle.casefold() for muscle in exercise["muscles_targeted"]}
        )
        and tags.issubset({tag.casefold() for tag in exercise["tags"]})
    ]
