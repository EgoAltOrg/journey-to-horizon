"""Where this wiki's config lives, shared by the sync and every gate so they
always agree.

The config (sync_config.py and the two allowlist JSONs) sits next to these
scripts by default. A wiki whose config names secrets keeps it outside the
public repo and sets WIKI_CONFIG_DIR to that folder. With the variable set,
every script that loads this module (the sync, and each check that reads the
config or resolves links) stops when:

  - the folder doesn't exist, instead of letting a check run without its
    allowlists (which would quietly drop per-wiki checks);
  - a config file is left in scripts/ as well: that copy would be ignored, and
    its reasons can name the secrets the move keeps out of the repo;
  - a config file it asks for is missing from the folder (config_path).
"""
import os
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
CONFIG_FILES = ("sync_config.py", "spoiler-leak-allowlist.json", "related-pages-allowlist.json")

_override = os.environ.get("WIKI_CONFIG_DIR")
CONFIG_DIR = Path(_override).expanduser().resolve() if _override else SCRIPTS_DIR
EXTERNAL = CONFIG_DIR != SCRIPTS_DIR

if EXTERNAL:
    if not CONFIG_DIR.is_dir():
        sys.exit(f"WIKI_CONFIG_DIR={_override} is not a folder; fix the path before running anything.")
    stray = [name for name in CONFIG_FILES if (SCRIPTS_DIR / name).exists()]
    if stray:
        sys.exit(
            f"WIKI_CONFIG_DIR points at {CONFIG_DIR}, but scripts/ also holds {', '.join(stray)}. "
            "That copy would be ignored, and it may name secrets in a public repo: move its "
            "content into the config folder and delete it from scripts/."
        )


def config_path(name):
    """A config file's path. An external config must have every file it is
    asked for: a missing one stops the script rather than running without it."""
    path = CONFIG_DIR / name
    if EXTERNAL and not path.exists():
        sys.exit(f"{name} is missing from WIKI_CONFIG_DIR ({CONFIG_DIR}).")
    return path


def shortest_key(slug):
    """The name Quartz's "shortest" link resolution matches a page by: the last
    path segment, with a folder's own index.md answering to the folder's name
    (so [[armada]] reaches locations/armada/index.md)."""
    parts = slug.split("/")
    if parts[-1] == "index" and len(parts) >= 2:
        return parts[-2]
    return parts[-1]
