"""Run fit_display_calibration with the middle-bucket precision floor overridden (candidate models only; the
shipped constant is unchanged). Usage: fit_floor_variant.py FLOOR -- <fit_display_calibration args>"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools/milk-analyzer'))
import fit_display_calibration as F
floor = float(sys.argv[1])
F.FACET_PRECISION_FLOOR.update({k: floor for k in ('balanced', 'drifting', 'normal')})
F.main(sys.argv[3:])
