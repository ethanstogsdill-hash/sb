"""Bootstrap script: create venv, install deps, install Playwright Chromium."""
import subprocess
import sys
import os

VENV_DIR = "venv"


def main():
    print("=== Sportsbook Dashboard Setup ===\n")

    # 1. Create virtual environment
    if not os.path.exists(VENV_DIR):
        print("[1/3] Creating virtual environment...")
        subprocess.check_call([sys.executable, "-m", "venv", VENV_DIR])
    else:
        print("[1/3] Virtual environment already exists.")

    # Determine pip path
    if os.name == "nt":
        pip = os.path.join(VENV_DIR, "Scripts", "pip.exe")
        python = os.path.join(VENV_DIR, "Scripts", "python.exe")
    else:
        pip = os.path.join(VENV_DIR, "bin", "pip")
        python = os.path.join(VENV_DIR, "bin", "python")

    # 2. Install Python deps
    print("[2/3] Installing Python dependencies...")
    subprocess.check_call([pip, "install", "-r", "requirements.txt"])

    # 3. Install Playwright Chromium
    print("[3/3] Installing Playwright Chromium browser...")
    subprocess.check_call([python, "-m", "playwright", "install", "chromium"])

    print("\n=== Setup complete! ===")
    print("\nNext steps:")
    print("  1. Copy .env.example to .env and fill in your credentials")
    print("  2. Activate the venv:")
    if os.name == "nt":
        print("       venv\\Scripts\\activate")
    else:
        print("       source venv/bin/activate")
    print("  3. Run the dashboard:")
    print("       python -m uvicorn app.main:app --reload")
    print("  4. Open http://localhost:8000")


if __name__ == "__main__":
    main()
