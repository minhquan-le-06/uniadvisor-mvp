"""Read KEY=value lines from a git-ignored .env into os.environ, without extra packages.

Looked for in the project root and in the current folder. Variables already set in the shell win over .env.
Tolerates what Windows editors and shells produce: UTF-8 with or without BOM, UTF-16 (PowerShell 5's
`echo ... > .env`), CRLF, `export KEY=...` / `set KEY=...` / `$env:KEY=...`, spaces around '=', quotes, and
comments. A `.env.txt` (Notepad adding .txt behind a hidden extension) is read too, with a warning.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from uniadvisor.paths import ROOT

log = logging.getLogger(__name__)

LINE = re.compile(r"^\s*(?:export\s+|set\s+|\$env:)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$", re.IGNORECASE)


def candidates() -> list[Path]:
    """Where a .env may be, in priority order (duplicates removed)."""
    out = []
    for d in (ROOT, Path.cwd()):
        for name in (".env", ".env.txt"):
            p = (d / name).resolve()
            if p not in out:
                out.append(p)
    return out


def read_text(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    if len(raw) > 1 and raw[1:2] == b"\x00":  # UTF-16 LE without a BOM
        return raw.decode("utf-16-le")
    return raw.decode("utf-8-sig", errors="replace")


def parse(text: str) -> dict[str, str]:
    out = {}
    for line in text.splitlines():
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
        out[key] = value.strip()
    return out


def load_dotenv(path: Path | None = None) -> list[str]:
    """Load `path`, or every candidate file that exists. Returns the names set (never the values)."""
    loaded = []
    for p in [path] if path is not None else candidates():
        if not p.exists():
            continue
        if p.name == ".env.txt":
            log.warning("reading %s: rename it to .env (Windows hid the .txt extension)", p)
        for key, value in parse(read_text(p)).items():
            if key not in os.environ:
                os.environ[key] = value
                loaded.append(key)
    return loaded


def describe() -> str:
    """What the loader can see, for error messages: files checked and the variable names in them."""
    lines = []
    for p in candidates():
        if p.exists():
            names = sorted(parse(read_text(p)))
            lines.append(f"  {p}: found, variables: {', '.join(names) or '(none parsed; expected lines like NAME=value)'}")
        else:
            lines.append(f"  {p}: not found")
    return "\n".join(lines)
