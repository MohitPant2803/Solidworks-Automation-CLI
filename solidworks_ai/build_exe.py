import os
import sys
import shutil
from pathlib import Path

def build() -> None:
    """Invokes PyInstaller programmatically to build a single-file executable."""
    print("Starting build process for SolidWorksAI...")
    
    # 1. Verify PyInstaller is installed
    try:
        import PyInstaller.__main__
    except ImportError:
        print("Error: PyInstaller is not installed. Please run: pip install pyinstaller")
        sys.exit(1)

    # Base workspace directory
    base_dir = Path(__file__).resolve().parent.parent
    entrypoint = base_dir / "main.py"
    
    if not entrypoint.exists():
        print(f"Error: Entrypoint file not found at {entrypoint}")
        sys.exit(1)

    # 2. Build pyinstaller argument list
    args = [
        str(entrypoint),
        "--onefile",
        "--name=SolidWorksAI",
        "--console",
        # Clean build folders before starting
        "--clean",
        # Ensure win32com submodules are fully bundled
        "--collect-submodules=win32com",
    ]

    print(f"Running PyInstaller with arguments: {' '.join(args)}")
    
    # 3. Trigger PyInstaller compilation
    try:
        PyInstaller.__main__.run(args)
        print("\n[OK] PyInstaller build finished successfully.")
        
        # 4. Copy generated EXE to workspace root for convenience
        dist_exe = base_dir / "dist" / "SolidWorksAI.exe"
        target_exe = base_dir / "SolidWorksAI.exe"
        
        if dist_exe.exists():
            shutil.copy2(dist_exe, target_exe)
            print(f"[OK] Copied SolidWorksAI.exe to workspace root: {target_exe}")
            
    except Exception as e:
        print(f"Error compiling executable: {e}")
        sys.exit(1)

if __name__ == "__main__":
    build()
