"""Entry point for Desktop Snake."""

import sys

from app import run
from engine.pets import SNAKE

if __name__ == "__main__":
    sys.exit(run(SNAKE))
