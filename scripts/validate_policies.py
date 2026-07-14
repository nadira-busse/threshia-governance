"""
Validate every policy document for unparsed restriction language.

Run with:
    python scripts/validate_policies.py

Exits non-zero if any policy contains restriction-like language ("never
permitted", "prohibited", "must not") that extract_never_permitted_actions()
didn't pick up — meaning that restriction would be silently unenforced by
the rule engine. Intended to run in CI alongside the test suite.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from threshia.policies.loader import load_all_policies
from threshia.rules.never_permitted import check_all_policies_for_unparsed_restrictions


def main() -> int:
    policies = load_all_policies()
    warnings = check_all_policies_for_unparsed_restrictions(policies)

    if not warnings:
        print(f"Checked {len(policies)} policy documents — no unparsed restrictions found.")
        return 0

    print(f"Found {len(warnings)} potential issue(s):\n")
    for warning in warnings:
        print(f"  - {warning}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
