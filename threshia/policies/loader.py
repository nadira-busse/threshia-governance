"""
Policy loader.

Reads markdown policy documents from threshia/policies/documents/ and parses
them into Policy objects (see threshia/models/policy.py).

File format:
    ---
    id: <string>
    category: <string>
    risk_level: <string>
    applicable_tools: [<string>, ...]
    source: <string>
    ---
    <markdown body>

The YAML block between the two `---` lines is the frontmatter. Everything
after the second `---` is stored as-is in Policy.content.
"""

from pathlib import Path

import yaml

from threshia.config import POLICIES_DIR
from threshia.models.policy import Policy

REQUIRED_FIELDS = {"id", "category", "risk_level", "applicable_tools", "source"}


class PolicyLoadError(Exception):
    """Raised when a policy document is missing or malformed."""


def _split_frontmatter(raw_text: str, file_path: str) -> tuple[dict, str]:
    """
    Split a document's raw text into (frontmatter_dict, body_text).

    Expects the file to start with '---', contain a YAML block, then a
    second '---' line, followed by the markdown body.
    """
    if not raw_text.startswith("---"):
        raise PolicyLoadError(
            f"{file_path}: file must start with '---' frontmatter delimiter."
        )

    # Split on the '---' delimiter. After removing the leading '---',
    # the next '---' closes the frontmatter block.
    parts = raw_text.split("---", 2)
    if len(parts) < 3:
        raise PolicyLoadError(
            f"{file_path}: could not find closing '---' for frontmatter block."
        )

    # parts[0] is empty (text before the first '---'), parts[1] is the YAML,
    # parts[2] is the markdown body.
    frontmatter_text = parts[1]
    body_text = parts[2].strip()

    try:
        frontmatter = yaml.safe_load(frontmatter_text)
    except yaml.YAMLError as e:
        raise PolicyLoadError(f"{file_path}: invalid YAML frontmatter — {e}")

    if not isinstance(frontmatter, dict):
        raise PolicyLoadError(
            f"{file_path}: frontmatter must be a YAML mapping (key: value pairs)."
        )

    return frontmatter, body_text


def _validate_frontmatter(frontmatter: dict, file_path: str) -> None:
    """Raise PolicyLoadError if any required field is missing."""
    missing = REQUIRED_FIELDS - frontmatter.keys()
    if missing:
        raise PolicyLoadError(
            f"{file_path}: missing required frontmatter field(s): {sorted(missing)}"
        )
    if not isinstance(frontmatter["applicable_tools"], list):
        raise PolicyLoadError(
            f"{file_path}: 'applicable_tools' must be a YAML list."
        )


def load_policy_file(path: Path) -> Policy:
    """Parse a single policy markdown file into a Policy object."""
    raw_text = path.read_text(encoding="utf-8")
    frontmatter, body = _split_frontmatter(raw_text, str(path))
    _validate_frontmatter(frontmatter, str(path))

    gated_tools = frontmatter.get("gated_tools", [])
    if not isinstance(gated_tools, list):
        raise PolicyLoadError(f"{path}: 'gated_tools' must be a YAML list.")

    return Policy(
        id=frontmatter["id"],
        category=frontmatter["category"],
        risk_level=frontmatter["risk_level"],
        applicable_tools=frontmatter["applicable_tools"],
        source=frontmatter["source"],
        content=body,
        file_path=str(path),
        gated_tools=gated_tools,
    )


def load_all_policies(policies_dir: Path | None = None) -> list[Policy]:
    """
    Load every .md file in the policies directory.

    Args:
        policies_dir: Override the default POLICIES_DIR (used in tests
                       to point at a temporary directory).

    Returns:
        A list of Policy objects, one per file, sorted by policy id.

    Raises:
        PolicyLoadError: if the directory doesn't exist, contains no
                          policy files, or any file fails to parse.
    """
    directory = policies_dir if policies_dir is not None else POLICIES_DIR

    if not directory.exists():
        raise PolicyLoadError(f"Policies directory does not exist: {directory}")

    policy_files = sorted(directory.glob("*.md"))
    if not policy_files:
        raise PolicyLoadError(f"No policy files (*.md) found in: {directory}")

    policies = [load_policy_file(f) for f in policy_files]
    return sorted(policies, key=lambda p: p.id)
