import os
import subprocess
import sys
from pathlib import Path


def _root_in(env_extra: dict, cwd: Path) -> str:
    env = {**os.environ, **env_extra}
    code = "from unidata.paths import ROOT; print(ROOT)"
    return subprocess.run([sys.executable, "-c", code], cwd=cwd, env=env, capture_output=True, text=True, check=True).stdout.strip()


def test_root_is_the_checkout():
    from unidata.paths import BACKEND_CONFIG, DATA_CONFIG, ROOT
    assert (ROOT / "pyproject.toml").exists() and DATA_CONFIG.is_dir() and BACKEND_CONFIG.is_dir()


def test_module_1_never_imports_the_backend():
    """Other modules build on module 1, never the other way round (data/unidata/__init__.py)."""
    import re

    from unidata.paths import DATA

    bad = [f"{f.relative_to(DATA)}:{i}" for f in (DATA / "unidata").rglob("*.py")
           for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1)
           if re.match(r"\s*(from|import) uniadvisor\b", line)]
    assert bad == []


def test_root_env_override(tmp_path):
    assert _root_in({"UNIADVISOR_ROOT": str(tmp_path)}, tmp_path) == str(tmp_path.resolve())
