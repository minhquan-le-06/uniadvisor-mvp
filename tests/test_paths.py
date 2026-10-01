import os
import subprocess
import sys
from pathlib import Path


def _root_in(env_extra: dict, cwd: Path) -> str:
    env = {**os.environ, **env_extra}
    code = "from uniadvisor.paths import ROOT; print(ROOT)"
    return subprocess.run([sys.executable, "-c", code], cwd=cwd, env=env, capture_output=True, text=True, check=True).stdout.strip()


def test_root_is_the_checkout():
    from uniadvisor.paths import CONFIG, ROOT
    assert (ROOT / "pyproject.toml").exists() and CONFIG.is_dir()


def test_root_env_override(tmp_path):
    assert _root_in({"UNIADVISOR_ROOT": str(tmp_path)}, tmp_path) == str(tmp_path.resolve())
