"""Locate the ns-3 build these runners drive.

This artifact deliberately does not vendor ns-3: the release is pinned by hash in
env/tarball.sha256, and the module is a self-contained contrib module that applies to an
unmodified ns-3.48 tree. Point NS3_DIR at your build:

    export NS3_DIR=/path/to/ns-3.48

The path is resolved but NOT checked at import, so --help still works without a build.
Call require() once in main(), before any worker is spawned -- a missing binary reported
by 24 parallel workers is 24 copies of the same unreadable traceback.
"""
import os
import sys
from pathlib import Path

# ../ns-3.48 relative to the repo root, i.e. a sibling of this checkout
_DEFAULT = Path(__file__).resolve().parents[1].parent / "ns-3.48"

SCENARIO = "build/scratch/ns3.48-eht-ra-gate1-optimized"
WIFI_MANAGER_EXAMPLE = "build/src/wifi/examples/ns3.48-wifi-manager-example-optimized"


def ns3_dir() -> Path:
    return Path(os.environ.get("NS3_DIR") or _DEFAULT).expanduser().resolve()


def binary(relpath: str) -> Path:
    """Path to an ns-3 build product. Existence is checked by require(), not here."""
    return ns3_dir() / relpath


def require(*paths: Path) -> None:
    missing = [p for p in paths if not p.exists()]
    if not missing:
        return
    sys.exit(
        "ns-3 build not found:\n"
        + "".join(f"  {p}\n" for p in missing)
        + f"\nNS3_DIR resolves to {ns3_dir()}"
        + ("  (default -- NS3_DIR is unset)\n" if not os.environ.get("NS3_DIR") else "\n")
        + "\nSet NS3_DIR to an ns-3.48 tree built with:\n"
          "  cp -r ns3/contrib/cqra        $NS3_DIR/contrib/\n"
          "  cp    ns3/scratch/*.cc        $NS3_DIR/scratch/\n"
          "  cd $NS3_DIR && ./ns3 configure --build-profile=optimized && ./ns3 build\n"
          "See README.md.")


def workers_default() -> int:
    """The campaigns in the paper ran 24-way on a 28-thread host."""
    return max(1, (os.cpu_count() or 4) - 4)
