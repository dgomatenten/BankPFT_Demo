"""Maker/Checker state machine for 4-Eyes Principle workflow."""

VALID_TRANSITIONS = {
    "DRAFT": ["PENDING"],
    "PENDING": ["APPROVED", "REJECTED"],
    "REJECTED": ["PENDING"],
    "APPROVED": ["PROCESSED"],
    "PROCESSED": [],
}


class WorkflowError(Exception):
    pass


def transition(current_status: str, target_status: str, maker_id: str, actor_id: str) -> None:
    """Validate a status transition.

    Rules:
    - Maker cannot approve their own submission (4-eyes).
    - Transition must be in the allowed map.
    """
    allowed = VALID_TRANSITIONS.get(current_status, [])
    if target_status not in allowed:
        raise WorkflowError(
            f"Invalid transition: {current_status} -> {target_status}. "
            f"Allowed: {allowed}"
        )
    if target_status == "APPROVED" and maker_id == actor_id:
        raise WorkflowError("Maker cannot approve their own submission (4-Eyes Principle).")
