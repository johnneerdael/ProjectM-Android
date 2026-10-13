"""Shared summary of a 150-frame RGB clip (frames 60-149) for the group measure (diagnostic only)."""
import numpy as np, cv2
W, H = 480, 270
LUMA = np.array([.2126, .7152, .0722], np.float32)


def summary(frames):
    """frames: (N, H, W, 3) float32 in [0,1], N >= 150."""
    f = frames[60:150]
    luma = f @ LUMA
    mx = f.max(-1); mn = f.min(-1)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    avg = f.mean(0)
    return {
        'luma': float(luma.mean()), 'rgb': f.mean((0, 1, 2)).astype(float).tolist(), 'saturation': float(sat.mean()),
        'frame_difference': float(np.abs(np.diff(f, axis=0)).mean()),
        'luma_series': (frames[:150] @ LUMA).mean((1, 2)).astype(float).tolist(),
        'avg_map': cv2.resize(avg, (60, 34), interpolation=cv2.INTER_AREA).astype(np.float32),
    }
