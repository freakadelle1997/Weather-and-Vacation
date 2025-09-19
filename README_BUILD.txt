----------------------------

bash -lc 'cd ~/Projects/Wetterdaten && chmod +x build_app.sh && ./build_app.sh'

----------------------------

cd ~/Projects/Wetterdaten
chmod +x build_app.sh


Dann ausführen:

./build_app.sh


Das Script erledigt alles (venv + Dependencies, PyInstaller-Build, DMG).
Falls ./build_app.sh „Permission denied“ sagt, häng einfach bash davor:

bash build_app.sh


Voraussetzungen:

Datei liegt wirklich in ~/Projects/Wetterdaten/build_app.sh

App.icns existiert im Projekt (oder passe im Script ICON_ICNS an).

Xcode Command Line Tools sind installiert (xcode-select --install, nur einmal nötig).

Ergebnis:

App unter dist/Wetterdaten.app

DMG im Projektordner Wetterdaten.dmg