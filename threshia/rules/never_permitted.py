"""
Never-permitted action extraction.

Each policy document lists actions that are never permitted for an
autonomous agent, formatted as a markdown bullet list of backtick-quoted
action names, introduced by a line containing "never permitted":

    **The following actions are never permitted for an autonomous agent:**

    - `approve_invoice`
    - `release_payment`

    These represent final financial authorization...

This module parses that list directly out of Policy.content, rather than
duplicating the same action names in a separate Python data structure.
The markdown is the single source of truth — a policy author only has to
update one place, and what the rule engine blocks always matches what the
document says it blocks.
"""

import re

from threshia.models.policy import Policy

NEVER_PERMITTED_MARKERS = (
    "never permitted",
    "not permitted",
    "must never be performed",
    "must not be performed",
)
BULLET_PATTERN = re.compile(r"^- `([^`]+)`$")

# Broader restriction-language signals, used only by the validation check
# below — not by extraction itself. A policy author might describe a
# restriction using one of these words without using the exact bullet-list
# convention the parser expects; that's the case this check is meant to catch.
RESTRICTION_SIGNAL_WORDS = ("never permitted", "not permitted", "prohibited", "must not")


def extract_never_permitted_actions(policy: Policy) -> set[str]:
    """
    Parse the "never permitted" bullet list out of a policy's markdown body.

    Returns an empty set if the policy has no such section (e.g. a policy
    that only ever ALLOWs or FLAGs, with nothing outright blocked).
    """
    actions: set[str] = set()
    in_block = False
    collected_in_block = False

    for line in policy.content.splitlines():
        stripped = line.strip()

        if not in_block:
            if any(marker in stripped.lower() for marker in NEVER_PERMITTED_MARKERS):
                in_block = True
                collected_in_block = False
            continue

        match = BULLET_PATTERN.match(stripped)
        if match:
            actions.add(match.group(1))
            collected_in_block = True
        elif stripped == "":
            continue  # blank lines inside/around the list don't end it
        elif collected_in_block:
            # Reached prose after the list — the block is over.
            in_block = False
        # else: still on the intro sentence before the list starts (it may
        # wrap onto a second line) — keep waiting for the first bullet.

    return actions


def extract_all_never_permitted_actions(policies: list[Policy]) -> dict[str, str]:
    """
    Build a combined lookup across every policy: action name -> policy id
    that blocks it. Used by the rule engine to check a single ToolCall
    against every loaded policy in one pass.

    If two policies block the same action name, the first policy in the
    list wins (policies are typically pre-sorted by id, so this is stable).
    """
    lookup: dict[str, str] = {}
    for policy in policies:
        for action in extract_never_permitted_actions(policy):
            lookup.setdefault(action, policy.id)
    return lookup


def check_policy_for_unparsed_restrictions(policy: Policy) -> list[str]:
    """
    Sanity check, not extraction: warn if a policy's prose contains
    restriction language (e.g. "prohibited", "must not") but the parser
    extracted zero never-permitted actions from it.

    This doesn't catch every possible way a restriction could be worded —
    it catches the common case of a policy author describing a
    restriction without using the bullet-list convention
    extract_never_permitted_actions() expects, which would otherwise mean
    that restriction is silently never enforced by the rule engine.

    Returns a list of human-readable warning strings (empty if nothing
    looks wrong).
    """
    if extract_never_permitted_actions(policy):
        return []  # something was parsed — no need to warn

    warnings = []
    lowered = policy.content.lower()
    for signal in RESTRICTION_SIGNAL_WORDS:
        if signal in lowered:
            warnings.append(
                f"Policy '{policy.id}' contains restriction language "
                f"('{signal}') but no never-permitted actions were parsed "
                f"from it. Check that the restriction uses the expected "
                f"Markdown bullet-list format."
            )
    return warnings


def check_all_policies_for_unparsed_restrictions(policies: list[Policy]) -> list[str]:
    """Run check_policy_for_unparsed_restrictions() across every policy."""
    all_warnings = []
    for policy in policies:
        all_warnings.extend(check_policy_for_unparsed_restrictions(policy))
    return all_warnings
