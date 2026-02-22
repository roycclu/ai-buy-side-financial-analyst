"""Entry point for the Buy-Side Financial Analyst Agent Team."""

import sys
import os

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.agent0_project_manager import ProjectManager


def main():
    ProjectManager().start()


if __name__ == "__main__":
    main()
