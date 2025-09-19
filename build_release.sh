#!/usr/bin/env bash
set -euo pipefail

APP_NAME="LCARSlite Weather and Vacation"

# immer relativ zum Skript arbeiten
cd "$(dirname "$0")"

# 1) venv anlegen/aktivieren
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

# 2) Abhängigkeiten installieren/aktualisieren
python -m pip install --upgrade pip wheel
pip install -r requirements.txt

# 3) Aufräumen
rm -rf build dist dmg_src "${APP_NAME}.dmg" ./*.spec

# 4) PyInstaller-Build (.app)
ICON_ARG=()
if [ -f "App.icns" ]; then
  ICON_ARG=(--icon "App.icns")
else
  echo "⚠️  App.icns nicht gefunden – baue ohne Icon."
fi

python -m PyInstaller \
  --noconfirm --clean --windowed \
  --name "${APP_NAME}" \
  "${ICON_ARG[@]}" \
  app.py

# 5) DMG vorbereiten
mkdir -p dmg_src
cp -R "dist/${APP_NAME}.app" dmg_src/
ln -s /Applications dmg_src/Applications || true

# 6) DMG erzeugen (ohne Rückfragen, überschreibt falls vorhanden)
hdiutil create -volname "${APP_NAME}" -srcfolder dmg_src -ov -format UDZO "${APP_NAME}.dmg"

echo
echo "✅ Fertig!"
echo "App:   $(pwd)/dist/${APP_NAME}.app"
echo "DMG:   $(pwd)/${APP_NAME}.dmg"
