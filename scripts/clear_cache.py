# scripts/clear_cache.py
import os
import sys
import shutil
from pathlib import Path

def clear_python_cache():
    """Clear all Python cache files."""
    project_root = Path(__file__).parent.parent
    
    # Clear __pycache__ directories
    pycache_dirs = list(project_root.rglob("__pycache__"))
    for cache_dir in pycache_dirs:
        print(f"Removing: {cache_dir}")
        shutil.rmtree(cache_dir, ignore_errors=True)
    
    # Clear .pyc files
    pyc_files = list(project_root.rglob("*.pyc"))
    for pyc_file in pyc_files:
        print(f"Removing: {pyc_file}")
        pyc_file.unlink(missing_ok=True)
    
    # Clear .pyo files
    pyo_files = list(project_root.rglob("*.pyo"))
    for pyo_file in pyo_files:
        print(f"Removing: {pyo_file}")
        pyo_file.unlink(missing_ok=True)
    
    print(f"✅ Cleared {len(pycache_dirs)} cache directories")
    print(f"✅ Cleared {len(pyc_files) + len(pyo_files)} compiled files")

if __name__ == "__main__":
    clear_python_cache()