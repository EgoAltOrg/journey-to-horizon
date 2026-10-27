#!/usr/bin/env python3
"""Unit tests for wiki_config.py: where the config is found, and each way an
external config stops a run. Each case imports the module in a fresh
interpreter, since it checks the config at import time.
Run: python3 scripts/test-wiki-config.py"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from wiki_config import shortest_key  # noqa: E402


def _import(scripts_dir, config_dir=None, then=""):
    """Import wiki_config from scripts_dir with WIKI_CONFIG_DIR set (or unset);
    return (exit code, stdout + stderr)."""
    env = {k: v for k, v in os.environ.items() if k != "WIKI_CONFIG_DIR"}
    if config_dir is not None:
        env["WIKI_CONFIG_DIR"] = str(config_dir)
    code = f"import sys; sys.path.insert(0, {str(scripts_dir)!r}); import wiki_config as w; {then}"
    r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def _bare_scripts(root):
    """A scripts/ folder holding only wiki_config.py, as in an external-config repo."""
    scripts = root / "scripts"
    scripts.mkdir()
    shutil.copy(HERE / "wiki_config.py", scripts)
    return scripts


def test_default_is_the_scripts_dir():
    code, out = _import(HERE, then="print(w.CONFIG_DIR, w.EXTERNAL)")
    assert code == 0, out
    assert out.strip() == f"{HERE} False", out


def test_external_config_is_used():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        scripts = _bare_scripts(root)
        cfg = root / "cfg"
        cfg.mkdir()
        (cfg / "sync_config.py").write_text("")
        code, out = _import(scripts, cfg, "print(w.config_path('sync_config.py'))")
        assert code == 0, out
        assert out.strip() == str((cfg / "sync_config.py").resolve()), out


def test_missing_external_folder_stops():
    with tempfile.TemporaryDirectory() as d:
        scripts = _bare_scripts(Path(d))
        code, out = _import(scripts, Path(d) / "nowhere")
        assert code != 0 and "is not a folder" in out, out


def test_config_left_in_scripts_stops():
    # A config file still in scripts/ while WIKI_CONFIG_DIR points elsewhere
    # must refuse: that copy would be ignored and may name secrets.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        scripts = _bare_scripts(root)
        (scripts / "related-pages-allowlist.json").write_text("{}")
        cfg = root / "cfg"
        cfg.mkdir()
        code, out = _import(scripts, cfg)
        assert code != 0 and "related-pages-allowlist.json" in out and "scripts/ also holds" in out, out


def test_missing_external_file_stops():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        scripts = _bare_scripts(root)
        cfg = root / "cfg"
        cfg.mkdir()
        code, out = _import(scripts, cfg, "w.config_path('spoiler-leak-allowlist.json')")
        assert code != 0 and "spoiler-leak-allowlist.json is missing" in out, out


def test_missing_default_file_is_allowed():
    # Without an external config, a gate may run with no allowlist file at all.
    code, out = _import(HERE, then="print(w.config_path('no-such-allowlist.json').name)")
    assert code == 0 and out.strip() == "no-such-allowlist.json", out


def test_shortest_key():
    assert shortest_key("ancestries/infernis") == "infernis"
    assert shortest_key("locations/polaris/index") == "polaris"
    assert shortest_key("pt/index") == "pt"
    assert shortest_key("index") == "index"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"  PASS {name}")
    print("All wiki_config tests passed.")
