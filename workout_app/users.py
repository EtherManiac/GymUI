"""Hard-coded workout profiles used by the lightweight user selector."""

from __future__ import annotations


USER_NAMES: dict[str, str] = {
    "tyler": "Tyler",
    "mia": "Mia",
    "dev": "Dev",
}


def user_name(user_id: str) -> str:
    """Return a display name while rejecting unknown profile identifiers."""

    try:
        return USER_NAMES[user_id]
    except KeyError as error:
        raise ValueError(f"Unknown workout profile: {user_id}") from error

