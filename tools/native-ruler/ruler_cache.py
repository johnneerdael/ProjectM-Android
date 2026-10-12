"""Cache decision for ruler results (standard library only, testable without cv2/numpy)."""
import hashlib,json
from pathlib import Path


def file_sha256(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''):h.update(chunk)
    return h.hexdigest()


def tree_identity(directory):
    """Identity of a library directory: sha256 over sorted relative names, sizes and file hashes."""
    h=hashlib.sha256();root=Path(directory)
    if root.is_dir():
        for p in sorted(root.rglob('*')):
            if p.is_file():h.update(f'{p.relative_to(root)}\0{p.stat().st_size}\0{file_sha256(p)}\n'.encode())
    return h.hexdigest()


def run_identity(preset_sha256,pcm_sha256,binary_sha256,swiftshader,config):
    return {'preset_sha256':preset_sha256,'pcm_sha256':pcm_sha256,'binary_sha256':binary_sha256,
            'swiftshader':swiftshader,'config':config}


def can_reuse(target,identity):
    """Reuse a cached result only when its recorded identity equals the current run's, input for input."""
    try:row=json.loads(Path(target).read_text())
    except (OSError,ValueError):return False
    return isinstance(row,dict) and row.get('identity')==identity
