#!/usr/bin/env bash
# One-time setup of an Ubuntu 24.04 machine (WSL2 on Windows works) for agent eval runs.
#
#   bash evals/agents/setup_ubuntu.sh            # everything, then the test suite as a check
#   SKIP_TESTS=1 bash evals/agents/setup_ubuntu.sh
#
# Installs what the agents' environment had in the 2026-10-18 run: Python 3 with the skill's
# requirements in a venv (~/s2q-venv, or $S2Q_VENV), Xvfb and the Qt xcb libraries, tesseract
# (tur + eng), Playwright with Chromium, Node 22, the skill's font and icon caches
# (~/.cache/screenshot-to-qml), and the Codex CLI. Takes 10-20 minutes and about 2 GB.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SKILL="$REPO/skills/screenshot-to-qml"
VENV="${S2Q_VENV:-$HOME/s2q-venv}"

echo "== system packages"
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip git curl zip unzip ca-certificates \
  xvfb xauth libxcb-cursor0 libxkbcommon-x11-0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
  libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-xinerama0 libxcb-xkb1 \
  libegl1 libgl1 libglib2.0-0 libfontconfig1 libdbus-1-3 \
  tesseract-ocr tesseract-ocr-tur tesseract-ocr-eng

if ! command -v node >/dev/null || [ "$(node -p 'process.versions.node.split(".")[0]')" -lt 20 ]; then
  echo "== Node 22"
  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
  sudo apt-get install -y nodejs
fi

echo "== Python venv: $VENV"
python3 -m venv "$VENV"
"$VENV/bin/pip" install -q -U pip
"$VENV/bin/pip" install -q -r "$SKILL/scripts/requirements.txt" playwright pytest
"$VENV/bin/python" -m playwright install --with-deps chromium

echo "== skill caches (fonts ~40 MB, icons ~170 MB)"
"$VENV/bin/python" "$SKILL/scripts/font_match.py" fetch
"$VENV/bin/python" "$SKILL/scripts/icon_match.py" fetch

if ! command -v codex >/dev/null; then
  echo "== Codex CLI"
  sudo npm install -g @openai/codex
fi

if [ -z "${SKIP_TESTS:-}" ]; then
  echo "== test suite (checks rendering, OCR and HTML extraction on this machine)"
  (cd "$REPO" && "$VENV/bin/python" -m pytest -q -p no:cacheprovider)
fi

cat <<EOF

Done. Next:
  codex login                                   # once; opens a browser (or prints a link)
  source $VENV/bin/activate
  cd $REPO
  python evals/prepare_run.py ~/runs/codex-v1.0 --cases 05,09,12,18 --skill skills/screenshot-to-qml
  python evals/run_agent.py ~/runs/codex-v1.0 --agent codex
EOF
