"""Compatibility import for archived research scripts; implementation moved."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from soundcore_audio.features import POLICY, analyze
