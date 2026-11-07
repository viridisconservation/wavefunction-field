# SPDX-License-Identifier: Apache-2.0
"""WFP simulator (pre-alpha bootstrap stub)."""

import argparse


def main() -> None:
    """Print bootstrap usage; serving and simulation are not implemented yet."""
    parser = argparse.ArgumentParser(prog='wf-sim', description='WFP simulator (pre-alpha bootstrap stub)')
    parser.parse_args()
    parser.print_help()


if __name__ == "__main__":
    main()
