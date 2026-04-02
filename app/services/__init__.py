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


def transition(current_status: str, target_status: str, maker_id, actor) -> None:
    """Validate a status transition with group-based permission checks.

    Rules:
    - Maker cannot approve their own submission (4-eyes).
    - Transition must be in the allowed map.
    - Actor must have the right group permission (can_make / can_check).
    """
    allowed = VALID_TRANSITIONS.get(current_status, [])
    if target_status not in allowed:
        raise WorkflowError(
            f"Invalid transition: {current_status} -> {target_status}. "
            f"Allowed: {allowed}"
        )

    # Check group permissions when actor is a User object
    if hasattr(actor, "can_make") and hasattr(actor, "can_check"):
        if target_status == "PENDING" and not actor.can_make:
            raise WorkflowError("You do not have Maker permission to submit uploads.")
        if target_status in ("APPROVED", "REJECTED") and not actor.can_check:
            raise WorkflowError("You do not have Checker permission to approve/reject uploads.")

    # 4-eyes: compare user IDs
    actor_id = actor.username if hasattr(actor, "username") else str(actor)
    maker_name = str(maker_id)
    if target_status == "APPROVED" and maker_name == actor_id:
        raise WorkflowError("Maker cannot approve their own submission (4-Eyes Principle).")
