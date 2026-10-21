"""Pure workout-selection and ordering logic that can be tested without UI."""

from __future__ import annotations

import random
from copy import deepcopy
from typing import Any


def ordered_slots(routine: dict[str, Any]) -> list[dict[str, Any]]:
    """Return routine slots in their explicit saved order."""

    return sorted(deepcopy(routine["slots"]), key=lambda slot: slot["order"])


def group_slots(slots: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Turn slots into movable units while keeping each superset together.

    Group members are placed at the position of their first member even if a
    hand-edited JSON file made them non-adjacent.
    """

    units: list[list[dict[str, Any]]] = []
    group_positions: dict[str, int] = {}
    for slot in slots:
        group_id = slot.get("superset_group_id")
        if not group_id:
            units.append([slot])
        elif group_id in group_positions:
            units[group_positions[group_id]].append(slot)
        else:
            group_positions[group_id] = len(units)
            units.append([slot])
    return units


def select_slots(routine: dict[str, Any], requested_count: int) -> list[dict[str, Any]]:
    """Fill the requested count when possible without splitting grouped sets.

    Exercise count is the primary goal and priority is the tie-breaker. A small
    dynamic program evaluates whole singles/groups and retains the lexicographically
    best priority choices for every reachable count. This can temporarily omit a
    higher-priority unit when a different combination exactly fills the request.
    Chosen slots are always returned in routine order.
    """

    units = group_slots(ordered_slots(routine))
    ranked_units = sorted(
        units,
        key=lambda unit: (unit[0]["priority"], unit[0]["order"]),
    )

    # Each state stores selected units plus a boolean priority signature. When
    # two combinations reach the same count, normal tuple comparison prefers
    # the one containing the earliest (highest-priority) ranked unit.
    states: dict[int, tuple[list[list[dict[str, Any]]], tuple[bool, ...]]] = {
        0: ([], ())
    }
    for unit in ranked_units:
        next_states: dict[int, tuple[list[list[dict[str, Any]]], tuple[bool, ...]]] = {}
        for exercise_count, (selected_units, signature) in states.items():
            candidates = [
                (exercise_count, selected_units, signature + (False,)),
            ]
            included_count = exercise_count + len(unit)
            if included_count <= requested_count:
                candidates.append(
                    (included_count, [*selected_units, unit], signature + (True,))
                )

            for candidate_count, candidate_units, candidate_signature in candidates:
                existing = next_states.get(candidate_count)
                if existing is None or candidate_signature > existing[1]:
                    next_states[candidate_count] = (candidate_units, candidate_signature)
        states = next_states

    best_count = max(states)
    selected = [slot for unit in states[best_count][0] for slot in unit]
    return sorted(selected, key=lambda slot: slot["order"])


def new_workout_snapshot(routine: dict[str, Any], requested_count: int) -> list[dict[str, Any]]:
    """Create session-only workout rows without altering the routine model."""

    return [
        {
            "slot": slot,
            "selected_exercise_id": slot["default_exercise_id"],
            "completed": False,
            "weight_used": "",
            # Base position tracks the active original/shuffled order separately
            # from the temporary completed-at-bottom display order.
            "base_position": position,
        }
        for position, slot in enumerate(select_slots(routine, requested_count))
    ]


def shuffle_snapshot(snapshot: list[dict[str, Any]], randomizer: random.Random | None = None) -> None:
    """Shuffle singles/supersets as units and mutate the active snapshot order."""

    randomizer = randomizer or random.Random()
    units = group_slots_by_snapshot(snapshot)
    randomizer.shuffle(units)
    snapshot[:] = [row for unit in units for row in unit]
    for position, row in enumerate(snapshot):
        row["base_position"] = position


def group_slots_by_snapshot(snapshot: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Group active rows by their slot's superset ID while preserving state."""

    units: list[list[dict[str, Any]]] = []
    group_positions: dict[str, int] = {}
    for row in snapshot:
        group_id = row["slot"].get("superset_group_id")
        if not group_id:
            units.append([row])
        elif group_id in group_positions:
            units[group_positions[group_id]].append(row)
        else:
            group_positions[group_id] = len(units)
            units.append([row])
    return units


def restore_snapshot_order(snapshot: list[dict[str, Any]]) -> None:
    """Restore routine order while retaining completion and substitutions."""

    snapshot.sort(key=lambda row: row["slot"]["order"])
    for position, row in enumerate(snapshot):
        row["base_position"] = position


def move_completed_units_to_end(snapshot: list[dict[str, Any]]) -> bool:
    """Move fully completed singles/supersets below incomplete workout units.

    A partially completed superset remains in its base position. Rebuilding from
    base positions on every call also means unchecking a row restores its proper
    original or shuffled location. The return value tells the UI whether it
    needs a rerun to display the new order.
    """

    # Sessions created before this feature may survive a Streamlit hot reload.
    # Seed their base positions from the currently visible order once.
    for position, row in enumerate(snapshot):
        row.setdefault("base_position", position)

    current_ids = [row["slot"]["id"] for row in snapshot]
    base_order = sorted(snapshot, key=lambda row: row["base_position"])
    units = group_slots_by_snapshot(base_order)
    incomplete_units = [unit for unit in units if not all(row["completed"] for row in unit)]
    completed_units = [unit for unit in units if all(row["completed"] for row in unit)]
    snapshot[:] = [row for unit in [*incomplete_units, *completed_units] for row in unit]
    return current_ids != [row["slot"]["id"] for row in snapshot]
