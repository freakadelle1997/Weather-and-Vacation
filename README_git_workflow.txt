# 1) Auf main wechseln und aktualisieren
git switch main
git pull origin main

# 2) Neuen Branch erstellen (sprechender Name)
git switch -c feature/region-tabs-formatierung

# 3) Arbeiten, Änderungen committen
git add .
git commit -m "Formatierung: Datum TT.MM.JJJJ in Region-Tabs"

# 4) Branch ins Remote pushen
git push -u origin feature/region-tabs-formatierung

# 5) Auf GitHub Pull Request öffnen und reviewen/mergen
