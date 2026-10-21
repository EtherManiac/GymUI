"""Profile calendar for scheduling and reviewing workout history."""

from __future__ import annotations

import calendar as calendar_module
from datetime import date, datetime, timezone
from uuid import uuid4

import streamlit as st

from workout_app.calendar_logic import (
    events_on_date,
    local_today,
    log_completed_workout,
    remove_calendar_event,
    schedule_routine,
    scheduled_event_on_date,
)
from workout_app.profile_ui import require_active_user
from workout_app.storage import DataLoadError, load_calendar, save_calendar
from workout_app.ui_helpers import (
    load_data_or_stop,
    render_data_portability,
    show_save_error,
)
from workout_app.validation import DataValidationError
from workout_app.workout_logic import new_workout_snapshot


def month_start(selected_date: date) -> date:
    """Return the first day of a date's month."""

    return selected_date.replace(day=1)


def shifted_month(current_month: date, offset: int) -> date:
    """Move a first-of-month date backward or forward by one month."""

    month_index = current_month.year * 12 + current_month.month - 1 + offset
    return date(month_index // 12, month_index % 12 + 1, 1)


active_user_id = require_active_user()
exercise_document, routine_document = load_data_or_stop(active_user_id)
render_data_portability(active_user_id, exercise_document, routine_document)

try:
    calendar_document = load_calendar(active_user_id)
except (DataLoadError, DataValidationError) as error:
    st.error("The calendar could not be loaded.")
    st.code(str(error))
    st.stop()

today = local_today()
selected_date_key = f"calendar_page_selected_date_{active_user_id}"
visible_month_key = f"calendar_page_visible_month_{active_user_id}"
if not isinstance(st.session_state.get(selected_date_key), date):
    st.session_state[selected_date_key] = today
if not isinstance(st.session_state.get(visible_month_key), date):
    st.session_state[visible_month_key] = month_start(today)

selected_date: date = st.session_state[selected_date_key]
visible_month: date = month_start(st.session_state[visible_month_key])

st.title("Calendar")
st.caption("Schedule upcoming routines and review completed workouts.")

st.html(
    """
    <style>
    /* Streamlit normally gives seven non-wrapping columns a minimum width and
       adds horizontal scrolling. Calendar rows instead divide the available
       page width evenly so weekday headings always align with their dates. */
    div[class*="st-key-calendar_grid_"] {
        max-width: 100%;
        overflow-x: clip;
    }
    div[class*="st-key-calendar_grid_"] [data-testid="stHorizontalBlock"] {
        display: flex;
        flex-wrap: nowrap !important;
        gap: 0.4rem !important;
        width: 100%;
        min-width: 0 !important;
        overflow: visible !important;
    }
    div[class*="st-key-calendar_grid_"] [data-testid="stColumn"] {
        flex: 1 1 0 !important;
        width: 0 !important;
        min-width: 0 !important;
    }
    div[class*="st-key-calendar_grid_week_"] button {
        min-width: 0 !important;
        min-height: 3rem;
        padding-left: 0.2rem;
        padding-right: 0.2rem;
    }
    @media (max-width: 640px) {
        div[class*="st-key-calendar_grid_"] [data-testid="stHorizontalBlock"] {
            gap: 0.2rem !important;
        }
        div[class*="st-key-calendar_grid_weekdays_"] p {
            font-size: 0.72rem;
        }
        div[class*="st-key-calendar_grid_week_"] button {
            min-height: 2.4rem;
            padding: 0.1rem !important;
        }
        div[class*="st-key-calendar_grid_week_"] button p {
            font-size: 0.72rem;
            white-space: nowrap;
        }
    }
    </style>
    """
)

previous_column, month_column, today_column, next_column = st.columns(
    [1, 5, 1.25, 1], vertical_alignment="center"
)
if previous_column.button(
    ":material/chevron_left:",
    key=f"calendar_previous_{active_user_id}",
    width="stretch",
):
    visible_month = shifted_month(visible_month, -1)
    st.session_state[visible_month_key] = visible_month
    st.session_state[selected_date_key] = visible_month
    st.rerun()
month_column.markdown(
    f"## {visible_month.strftime('%B %Y')}", text_alignment="center"
)
if today_column.button(
    "Today",
    key=f"calendar_today_{active_user_id}",
    width="stretch",
):
    st.session_state[visible_month_key] = month_start(today)
    st.session_state[selected_date_key] = today
    st.rerun()
if next_column.button(
    ":material/chevron_right:",
    key=f"calendar_next_{active_user_id}",
    width="stretch",
):
    visible_month = shifted_month(visible_month, 1)
    st.session_state[visible_month_key] = visible_month
    st.session_state[selected_date_key] = visible_month
    st.rerun()

with st.container(key="calendar_grid_weekdays"):
    weekday_columns = st.columns(7, gap="small", wrap=False)
    for column, weekday in zip(
        weekday_columns, ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
    ):
        column.markdown(f"**{weekday}**", text_alignment="center")

month_weeks = calendar_module.monthcalendar(
    visible_month.year, visible_month.month
)
events_by_date: dict[str, set[str]] = {}
for event in calendar_document["events"]:
    events_by_date.setdefault(event["date"], set()).add(event["status"])

for week_index, week in enumerate(month_weeks):
    with st.container(key=f"calendar_grid_week_{week_index}"):
        day_columns = st.columns(7, gap="small", wrap=False)
        for weekday_index, day_number in enumerate(week):
            column = day_columns[weekday_index]
            if day_number == 0:
                column.button(
                    " ",
                    key=(
                        f"calendar_empty_{active_user_id}_{visible_month.isoformat()}_"
                        f"{week_index}_{weekday_index}"
                    ),
                    disabled=True,
                    width="stretch",
                )
                continue

            cell_date = date(visible_month.year, visible_month.month, day_number)
            statuses = events_by_date.get(cell_date.isoformat(), set())
            markers = ""
            if "completed" in statuses:
                markers += " ●"
            if "scheduled" in statuses:
                markers += " ○"
            if column.button(
                f"{day_number}{markers}",
                key=f"calendar_day_{active_user_id}_{cell_date.isoformat()}",
                type="primary" if cell_date == selected_date else "secondary",
                width="stretch",
            ):
                st.session_state[selected_date_key] = cell_date
                st.rerun()

st.caption("● Completed   ○ Scheduled")
st.divider()

selected_date = st.session_state[selected_date_key]
st.subheader(selected_date.strftime("%A, %B %d, %Y").replace(" 0", " "))
selected_events = events_on_date(calendar_document, selected_date)
if not selected_events:
    st.info("Nothing is logged or scheduled for this date.")

for event in selected_events:
    with st.container(border=True):
        status_label = "Scheduled" if event["status"] == "scheduled" else "Completed"
        st.markdown(f"### {status_label}: {event['routine_name']}")
        if event["status"] == "completed":
            completed_exercises = event.get("exercises", [])
            st.caption(f"{len(completed_exercises)} exercises logged")
            for exercise in completed_exercises:
                weight_used = exercise.get("weight_used", "") or "Not entered"
                st.write(
                    f"{exercise['exercise_name']} — {exercise['sets']} × "
                    f"{exercise['reps']} — Weight used: {weight_used}"
                )

        remove_label = (
            "Remove scheduled workout"
            if event["status"] == "scheduled"
            else "Remove completed workout"
        )
        if st.button(
            remove_label,
            key=f"calendar_remove_event_{active_user_id}_{event['id']}",
        ):
            try:
                save_calendar(
                    active_user_id,
                    remove_calendar_event(calendar_document, event["id"]),
                )
            except (DataLoadError, DataValidationError) as error:
                show_save_error(error)
            else:
                if event["status"] == "scheduled" and selected_date == today:
                    st.session_state.pop("todays_scheduled_routine_id", None)
                    st.session_state.pop("calendar_scheduled_event_id", None)
                st.rerun()

st.divider()
st.subheader("Add a calendar entry")
routines = sorted(
    routine_document["routines"], key=lambda routine: routine["name"].casefold()
)
routine_by_id = {routine["id"]: routine for routine in routines}
if not routines:
    st.info("Create a routine before adding calendar entries.")
    st.stop()

scheduled_event = scheduled_event_on_date(calendar_document, selected_date)
scheduled_routine_id = (
    scheduled_event["routine_id"]
    if scheduled_event and scheduled_event["routine_id"] in routine_by_id
    else None
)
routine_ids = list(routine_by_id)
selected_routine_id = st.selectbox(
    "Routine",
    options=routine_ids,
    index=(
        routine_ids.index(scheduled_routine_id)
        if scheduled_routine_id is not None
        else 0
    ),
    format_func=lambda routine_id: routine_by_id[routine_id]["name"],
    key=f"calendar_page_routine_{active_user_id}_{selected_date.isoformat()}",
)
selected_routine = routine_by_id[selected_routine_id]
routine_is_empty = not selected_routine["slots"]
if routine_is_empty:
    st.caption("This routine has no exercises yet.")

action_columns = st.columns(2)
if selected_date >= today and action_columns[0].button(
    "Schedule workout",
    key=f"calendar_page_schedule_{active_user_id}_{selected_date.isoformat()}",
    type="primary",
    disabled=routine_is_empty,
    width="stretch",
):
    updated_calendar, event_id = schedule_routine(
        calendar_document,
        selected_date,
        selected_routine,
        event_id=str(uuid4()),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    try:
        save_calendar(active_user_id, updated_calendar)
    except (DataLoadError, DataValidationError) as error:
        show_save_error(error)
    else:
        if selected_date == today:
            st.session_state.workout_routine_id = selected_routine_id
            st.session_state.calendar_scheduled_event_id = event_id
            st.session_state.pop("active_workout_identity", None)
            st.session_state.open_scheduled_workout_requested = True
        st.rerun()

if selected_date <= today and action_columns[1].button(
    "Log completed workout",
    key=f"calendar_page_log_{active_user_id}_{selected_date.isoformat()}",
    disabled=routine_is_empty,
    width="stretch",
):
    exercise_by_id = {
        exercise["id"]: exercise for exercise in exercise_document["exercises"]
    }
    snapshot = new_workout_snapshot(selected_routine, len(selected_routine["slots"]))
    updated_calendar, _ = log_completed_workout(
        calendar_document,
        selected_date,
        selected_routine,
        snapshot,
        exercise_by_id,
        event_id=str(uuid4()),
        workout_session_id=f"manual-{uuid4()}",
        completed_at=datetime.now(timezone.utc).isoformat(),
        source="manual",
    )
    try:
        save_calendar(active_user_id, updated_calendar)
    except (DataLoadError, DataValidationError) as error:
        show_save_error(error)
    else:
        st.rerun()
