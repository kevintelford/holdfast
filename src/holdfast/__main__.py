"""CLI entry point: python -m holdfast status <contract_dir>"""

import sys

from .status import main

if __name__ == "__main__":
    sys.exit(main())
