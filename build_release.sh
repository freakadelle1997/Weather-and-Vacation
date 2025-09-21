#!/usr/bin/env bash
set -euo pipefail

# --- Konfiguration ---
APP_NAME="LCARSlite Weather and Vacation"
BUNDLE_ID="com.lcarslite.weather.vacation"
ENTRYPOINT="app.py"                     # Start-Skript deiner App
ICON_FILE="App.icns"                    # .icns im Projektverzeichnis
VENV_DIR=".venv"                        # Virtuelle Umgebung
REQ_FILE="requirements.txt"             # Python-Abhängigkeiten
DIST_DIR="dist"
BUILD_DIR="build"

# Optional: zusätzliche Ressourcen (CSV usw.) in den Build aufnehmen
# Alles im Ordner "data" wird in der App unter Contents/Resources/data/ verfügbar.
RES_DIR="data"
ADD_DATA_ARGS=()
if [ -d "$RES_DIR" ]; then
  ADD_DATA_ARGS+=( --add-data "$RES_DIR:data" )
fi

# Sammle Daten/Hidden-Imports für kompliziertere Pakete
COLLECT_ARGS=(
  --collect-all wetterdienst
  --collect-all pandas
  --collect-all polars
  --collect-submodules PyQt6
  --collect-submodules PyQt6.QtNetwork
)


# --- Vorbereitung ---
echo "==> Aufräumen"
rm -rf "$DIST_DIR" "$BUILD_DIR"

echo "==> Virtuelle Umgebung prüfen/anlegen: $VENV_DIR"
if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi

echo "==> Venv aktivieren & Abhängigkeiten installieren"
# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip wheel setuptools
if [ -f "$REQ_FILE" ]; then
  pip install -r "$REQ_FILE"
else
  echo "WARN: $REQ_FILE nicht gefunden – installiere nur PyInstaller."
  pip install pyinstaller
fi

# --- PyInstaller Build (.app) ---
echo "==> Baue .app mit PyInstaller"
if [ ! -f "$ICON_FILE" ]; then
  echo "WARN: $ICON_FILE nicht gefunden – App nutzt Standard-Icon."
  ICON_ARG=()
else
  ICON_ARG=( --icon "$ICON_FILE" )
fi

python -m PyInstaller \
  --noconfirm \
  --windowed \
  --name "$APP_NAME" \
  --osx-bundle-identifier "$BUNDLE_ID" \
  "${ICON_ARG[@]}" \
  "${COLLECT_ARGS[@]}" \
  "${ADD_DATA_ARGS[@]}" \
  "$ENTRYPOINT"

# --- DMG bauen ---
echo "==> Erzeuge DMG"
APP_PATH="$DIST_DIR/$APP_NAME.app"
DMG_PATH="$DIST_DIR/$APP_NAME.dmg"

if [ ! -d "$APP_PATH" ]; then
  echo "FEHLER: App-Bundle nicht gefunden: $APP_PATH"
  exit 1
fi

# Optional: hübsches DMG mit Applications-Link
STAGE_DIR="$DIST_DIR/_dmg_stage"
rm -rf "$STAGE_DIR"
mkdir -p "$STAGE_DIR"
cp -R "$APP_PATH" "$STAGE_DIR/"
ln -s /Applications "$STAGE_DIR/Applications"

hdiutil create -volname "$APP_NAME" -srcfolder "$STAGE_DIR" -ov -format UDZO "$DMG_PATH" >/dev/null

# Aufräumen Stage
rm -rf "$STAGE_DIR"

echo "==> Fertig!"
echo "App: $APP_PATH"
echo "DMG: $DMG_PATH"
