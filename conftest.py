"""Pytest config: đảm bảo project root nằm trong sys.path để import `src.*`."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
