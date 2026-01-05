#!/bin/bash

# Pfade definieren
# Ermittelt das Verzeichnis, in dem dieses Skript liegt
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
PROJECT_DIR=$(dirname "$SCRIPT_DIR")
DB_FILE="$PROJECT_DIR/db.sqlite3"
MEDIA_DIR="$PROJECT_DIR/media"
BACKUP_DIR="$PROJECT_DIR/backups"
TEMP_RESTORE="/tmp/restore_temp"

# 1. Auswahl des Backups
if [ -z "$1" ]; then
    echo "Verfügbare Backups im Verzeichnis $BACKUP_DIR:"
    ls -1 "$BACKUP_DIR"/*.tar.gz
    echo ""
    echo "Nutzung: $0 <dateiname_des_backups>"
    exit 1
fi

BACKUP_PATH="$1"

# Falls nur der Dateiname ohne Pfad angegeben wurde
if [[ ! "$BACKUP_PATH" == /* ]]; then
    BACKUP_PATH="$BACKUP_DIR/$BACKUP_PATH"
fi

if [ ! -f "$BACKUP_PATH" ]; then
    echo "FEHLER: Backup-Datei nicht gefunden: $BACKUP_PATH"
    exit 1
fi

echo "--- Starte Wiederherstellung von: $(basename "$BACKUP_PATH") ---"

# 2. Dienste stoppen (Wichtig für Datenkonsistenz)
echo "Stoppe Gunicorn..."
sudo systemctl stop gunicorn

# 3. Sicherheitskopie des aktuellen Standes erstellen (falls der Restore fehlschlägt)
echo "Erstelle Notfall-Kopie des aktuellen Standes..."
cp "$DB_FILE" "${DB_FILE}.pre_restore_bak"
tar -czf "${BACKUP_DIR}/pre_restore_media_bak.tar.gz" -C "$PROJECT_DIR" media

# 4. Entpacken in temporäres Verzeichnis
echo "Entpacke Backup..."
rm -rf "$TEMP_RESTORE" && mkdir -p "$TEMP_RESTORE"
tar -xzf "$BACKUP_PATH" -C "$TEMP_RESTORE"

# 5. Daten zurückspielen
echo "Stelle Dateien wieder her..."

# Datenbank ersetzen (Nutzt die temporäre DB aus dem Archiv)
if [ -f "$TEMP_RESTORE/temp_db.sqlite3" ]; then
    mv "$TEMP_RESTORE/temp_db.sqlite3" "$DB_FILE"
    # Rechte korrigieren
    sudo chown pi:www-data "$DB_FILE"
    sudo chmod 664 "$DB_FILE"
fi

# Media-Ordner ersetzen
if [ -d "$TEMP_RESTORE/media" ]; then
    rm -rf "$MEDIA_DIR"
    mv "$TEMP_RESTORE/media" "$MEDIA_DIR"
    # Rechte korrigieren
    sudo chown -R pi:www-data "$MEDIA_DIR"
    sudo chmod -R 755 "$MEDIA_DIR"
fi

# 6. Aufräumen und Starten
rm -rf "$TEMP_RESTORE"

echo "Starte Dienste wieder..."
sudo systemctl start gunicorn

# Optional: Nginx reload (meist nicht nötig, aber sicher ist sicher)
sudo systemctl reload nginx

echo "--- WIEDERHERSTELLUNG ERFOLGREICH ABGESCHLOSSEN ---"
echo "Hinweis: Deine aktuelle Datenbank wurde ersetzt."