#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-py}"
VENV_DIR="${VENV_DIR:-./buildenv}"
EXE_NAME="${EXE_NAME:-AttendanceSystem}"
OUTPUT_ZIP="${OUTPUT_ZIP:-AttendanceSystem-release.zip}"
DATA_DIR="${DATA_DIR:-./data}"

usage() {
  cat <<EOF
Usage: ./build_release.sh [options]

Options:
  --python <command>      Python launcher to use (default: py)
  --venv-dir <path>       Virtual environment directory (default: ./buildenv)
  --exe-name <name>       Output exe base name (default: AttendanceSystem)
  --output-zip <path>     Output zip bundle path (default: AttendanceSystem-release.zip)
  --data-dir <path>       Data directory to bundle (default: ./data)
  -h, --help              Show this help message
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --python)
      PYTHON_BIN="$2"
      shift 2
      ;;
    --venv-dir)
      VENV_DIR="$2"
      shift 2
      ;;
    --exe-name)
      EXE_NAME="$2"
      shift 2
      ;;
    --output-zip)
      OUTPUT_ZIP="$2"
      shift 2
      ;;
    --data-dir)
      DATA_DIR="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

run_cmd() {
  echo
  echo "> $*"
  "$@"
}

echo "=== Build and release script for AttendanceSystem ==="
echo "This script sets up a venv, installs dependencies, verifies OpenCV, builds the exe, and packages a zip bundle."

if [[ ! -d "$VENV_DIR" ]]; then
  if command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    run_cmd "$PYTHON_BIN" -m venv "$VENV_DIR"
  else
    echo "Python launcher not found: $PYTHON_BIN" >&2
    exit 1
  fi
fi

VENV_PYTHON="$VENV_DIR/Scripts/python.exe"
VENV_PYINSTALLER="$VENV_DIR/Scripts/pyinstaller.exe"

if [[ ! -f "$VENV_PYTHON" ]]; then
  echo "Virtual environment Python not found at $VENV_PYTHON" >&2
  exit 1
fi

run_cmd "$VENV_PYTHON" -m pip install --upgrade pip
run_cmd "$VENV_PYTHON" -m pip install -r requirements.txt pyinstaller

echo

echo "Verifying OpenCV import and required APIs..."
"$VENV_PYTHON" -c "import cv2; print(cv2.__file__); print(cv2.__version__); print(hasattr(cv2,'CascadeClassifier'), hasattr(cv2,'VideoCapture'), hasattr(cv2,'face'))"

echo

echo "Building the executable with PyInstaller..."
run_cmd "$VENV_PYINSTALLER" --onefile --windowed --name "$EXE_NAME" --collect-data cv2 app.py

echo

echo "Creating the release zip bundle..."
run_cmd "$VENV_PYTHON" release_bundle.py --exe "dist/$EXE_NAME.exe" --data "$DATA_DIR" --output "$OUTPUT_ZIP"

echo

echo "Release bundle created: $OUTPUT_ZIP"
echo "If you want to publish this artifact, upload the zip file; end users should unzip it and keep AttendanceSystem.exe next to data/."
