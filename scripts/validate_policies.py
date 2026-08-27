"""
Validate every policy document against the structured policy contract.

Run with:
    python scripts/validate_policies.py

Deterministic governance rules (applicable_tools, gated_tools,
never_permitted) are read from validated YAML frontmatter, not parsed
from Markdown prose (see threshia/policies/loader.py). Loading a policy
document already fails closed on any malformed frontmatter — a missing
required field, a non-list value, a null/number/boolean/nested/duplicate/
whitespace-only never_permitted entry, or an empty never_permitted list
all raise PolicyLoadError. This script's job is exactly that: run every
repository policy document through the real loader and report the first
failure clearly, so a broken policy document is caught before the engine
ever runs — independent of, and faster than, running the full test suite.
Intended to run in CI alongside the test suite.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from threshia.policies.loader import PolicyLoadError, load_all_policies


def main() -> int:
    try:
        policies = load_all_policies()
    except PolicyLoadError as e:
        print(f"Policy validation failed: {e}")
        return 1

    total_never_permitted = sum(len(p.never_permitted) for p in policies)
    print(f"Checked {len(policies)} policy document(s) — all frontmatter valid.")
    for policy in policies:
        print(
            f"  - {policy.id}: {len(policy.applicable_tools)} applicable tool(s), "
            f"{len(policy.gated_tools)} gated, "
            f"{len(policy.never_permitted)} never-permitted action(s)"
        )
    print(f"Total never-permitted actions across all policies: {total_never_permitted}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
