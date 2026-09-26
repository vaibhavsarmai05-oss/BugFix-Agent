import sys
import os

# Allow  `from calculator import ...`  to resolve to
# demo_project/calculator_bug/calculator.py
# regardless of which directory pytest is invoked from.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
