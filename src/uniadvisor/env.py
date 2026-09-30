"""Read KEY=value lines from the project's .env (git-ignored) into os.environ, without extra packages.

Variables already set in the shell win over .env. Supports comments (#), blank lines, `export KEY=...`,
and single or double quotes around the value.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from uniadvisor.paths import ROOT

LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")


def load_dotenv(path: Path = ROOT / ".env") -> list[str]:
    """Returns the names set from the file (never the values)."""
    if not path.exists():
        return []
    loaded = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = LINE.match(line)
        if not m:
            continue
        key, value = m.groups()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        else:
            value = re.sub(r"\s+#.*$", "", value)  # trailing comment on an unquoted value
        if key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
    return loaded
