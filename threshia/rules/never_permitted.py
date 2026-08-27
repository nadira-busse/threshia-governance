"""
Never-permitted action lookup.

Each policy's deterministic hard-block list lives in its `never_permitted`
YAML frontmatter field (see threshia/models/policy.py, validated at load
time by threshia/policies/loader.py) — not in Markdown prose. This module
only combines that already-validated, structured data across every loaded
policy into a single action-name -> policy-id lookup the rule engine can
check a ToolCall against in one pass.

Earlier versions of this module parsed the never-permitted list directly
out of policy Markdown body text (a heading phrase + a bullet list of
backtick-quoted names). That approach made deterministic enforcement
dependent on prose formatting: a misspelled heading, a missing backtick,
or a stray bullet character could silently reduce the blocked-action set
with no error and no warning. Reading directly from validated frontmatter
makes that class of failure impossible: a malformed `never_permitted`
value now fails to load at all (PolicyLoadError), and once loaded,
nothing about the Markdown body can change what this module returns —
see tests/test_never_permitted.py for the regression coverage.
"""

from threshia.models.policy import Policy


def build_never_permitted_lookup(policies: list[Policy]) -> dict[str, str]:
    """
    Build a combined lookup across every policy: action name -> policy id
    that blocks it. Used by the rule engine to check a single ToolCall
    against every loaded policy's structured never_permitted list in one
    pass.

    If two policies block the same action name, the first policy in the
    list wins (policies are typically pre-sorted by id, so this is stable).
    """
    lookup: dict[str, str] = {}
    for policy in policies:
        for action in policy.never_permitted:
            lookup.setdefault(action, policy.id)
    return lookup
