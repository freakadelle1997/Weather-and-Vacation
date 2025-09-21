#!/usr/bin/env bash
set -euo pipefail

APP_NAME="LCARSlite Weather and Vacation"
BUNDLE_ID="com.lcarslite.weather.vacation"
ENTRY="app.py"

# Aufräumen
rm -rf build dist

# App bundlen – wichtig: holidays-Module einsammeln
pyinstaller "$ENTRY" \
  --name "$APP_NAME" \
  --windowed \
  --osx-bundle-identifier "$BUNDLE_ID" \
  --icon "icons/app.icns" \
  --add-data "Data/school_holidays.csv:Data" \
  --collect-all holidays \
  --clean

# Optional: DMG erzeugen, falls create-dmg installiert ist
if command -v create-dmg >/dev/null 2>&1; then
  rm -f "dist/${APP_NAME}.dmg" || true
  create-dmg \
    --overwrite \
    --volname "${APP_NAME} Installer" \
    --window-pos 200 120 \
    --window-size 600 400 \
    --icon-size 120 \
    --app-drop-link 425 200 \
    "dist/${APP_NAME}.dmg" \
    "dist/${APP_NAME}.app"
else
  echo "Hinweis: 'create-dmg' nicht gefunden – .app liegt in dist/, DMG-Erstellung übersprungen."
fi
