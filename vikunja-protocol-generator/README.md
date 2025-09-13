# Vikunja Protocol Generator

Ein Python-Skript zur automatischen Generierung von deutschen Sitzungsprotokollen aus Vikunja-Aufgaben.

## Installation

1. Pandoc installieren:
   ```bash
   # Ubuntu/Debian
   sudo apt install pandoc
   
   # macOS/Universal Blue (Bluefin OS, ...)
   brew install pandoc
   
   # Windows
   # Download von https://pandoc.org/installing.html
   ```

2. Python-Abhängigkeiten installieren:
   ```bash
   pip install -r requirements.txt
   ```

3. Umgebungsvariablen konfigurieren:
   - Kopiere `.env` und passe die Werte an:
     - `VIKUNJA_BASE_URL`: URL deiner Vikunja-Instanz
     - `VIKUNJA_API_TOKEN`: API-Token für die Authentifizierung
     - `META_TASK_ID`: ID der Meta-Aufgabe mit Tagesordnungspunkten
     - `MIN_COMMENTS`: Mindestanzahl Kommentare (Standard: 2)

## Verwendung

```bash
python vikunja_protocol.py
```

Das Skript:
1. Lädt Aufgaben und Kommentare von Vikunja
2. Generiert ein deutsches Protokoll mit Jinja2-Template
3. Speichert das Protokoll unter `../{Jahr}/{YYYY-MM-DD} - {Titel}.md`

## Projektstruktur

```
├── src/                              # Python-Module
│   ├── config.py                     # Konfigurationsverwaltung
│   ├── vikunja_client.py            # Vikunja API-Client
│   └── formatters.py                # Jinja2-Filter
├── templates/                        # Jinja2-Templates
│   └── makerspace_protocol_template.md.j2
├── vikunja_protocol.py              # Hauptskript
└── requirements.txt                 # Python-Abhängigkeiten
```
