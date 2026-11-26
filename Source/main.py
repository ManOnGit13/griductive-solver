"""Run with: python main.py [path/to/puzzle.json]."""

import argparse
from pathlib import Path
import tkinter as tk

from gui import GriductiveApp


def main():
    parser = argparse.ArgumentParser(description="Griductive Solver desktop application")
    parser.add_argument("puzzle", nargs="?", type=Path, help="Puzzle JSON to open")
    args = parser.parse_args()
    root = tk.Tk()
    GriductiveApp(root, args.puzzle)
    root.mainloop()


if __name__ == "__main__":
    main()
