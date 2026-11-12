"""Entry point. Sets up portable paths before anything else is imported."""
import sys

from mimamori import paths

paths.make_portable_env()

from mimamori.gui import run  # noqa: E402

if __name__ == "__main__":
    sys.exit(run(start_minimized="--minimized" in sys.argv, quit_running="--quit" in sys.argv))
