In Projektordner gehen

    cd ~/Projects/Wetterdaten

-----------------

Virtuelle Umgebung einrichten

    python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip wheel setuptools
pip install PyQt6 wetterdienst pandas polars tzdata certifi


-----------------

App starten

    python dwd_regions_gui.py


-----------------




