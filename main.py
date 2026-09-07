"""Entry point for Desktop Kitten."""

import sys

from app import run
from engine.pets import KITTEN

if __name__ == "__main__":
    sys.exit(run(KITTEN))
