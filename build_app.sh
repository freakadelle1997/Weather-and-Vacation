#!/usr/bin/env bash
set -euo pipefail

APP_NAME="Wetterdaten"
ICON_ICNS="App.icns"     # falls nicht vorhanden: vorher aus icon.png erzeugen
MAIN_PY="dwd_regions_gui.py"

cd "$(dirname "$0")"

echo ">>> 1) venv + deps"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip install --upgrade pip wheel
pip install PyQt6 wetterdienst pandas polars pyinstaller tzdata certifi

echo ">>> 2) Build .app"
rm -rf build dist *.spec
pyinstaller --windowed --name "$APP_NAME" --icon "$ICON_ICNS" \
  --collect-data wetterdienst --collect-submodules wetterdienst \
  --collect-data pandas --collect-submodules pandas \
  --collect-data tzdata --collect-data certifi \
  --collect-data polars --collect-submodules polars \
  "$MAIN_PY"

echo ">>> 3) DMG vorbereiten"
rm -rf dmg_src Wetterdaten.dmg
mkdir -p dmg_src
cp -R "dist/${APP_NAME}.app" dmg_src/
ln -s /Applications dmg_src/Applications

echo ">>> 4) DMG erstellen"
hdiutil create -volname "$APP_NAME" \
  -srcfolder dmg_src \
  -ov -format UDZO \
  "${APP_NAME}.dmg"

echo "Fertig:"
echo "  - App: dist/${APP_NAME}.app"
echo "  - DMG: ${APP_NAME}.dmg"
