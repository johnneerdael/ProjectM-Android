"""Candidate: every facet classifier option held to at least FLOOR precision (shipped constants unchanged)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools/milk-analyzer'))
import fit_display_calibration as F
floor = float(sys.argv[1])
for o in F.FACET_CLASSIFIER_OPTIONS: F.FACET_PRECISION_FLOOR[o] = max(F.FACET_PRECISION_FLOOR.get(o, 0.), floor)
F.main(sys.argv[3:])
