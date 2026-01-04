#!/bin/bash

# Pfade definieren
PROJECT_DIR="/home/pi/skg-notenbank"
DB_FILE="$PROJECT_DIR/db.sqlite3"
BACKUP_DIR="$PROJECT_DIR/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="db_backup_$TIMESTAMP.sqlite3"

# Backup-Verzeichnis erstellen, falls nicht vorhanden
mkdir -p "$BACKUP_DIR"

# SQLite Backup-Befehl ausführen (sicherer als einfaches Kopieren)
sqlite3 "$DB_FILE" ".backup '$BACKUP_DIR/$BACKUP_NAME'"

# Erfolg prüfen
if [ $? -eq 0 ]; then
    echo "Backup erfolgreich erstellt: $BACKUP_DIR/$BACKUP_NAME"
    # Optional: Alte Backups löschen, die älter als 30 Tage sind
    find "$BACKUP_DIR" -name "*.sqlite3" -type f -mtime +30 -delete
else
    echo "FEHLER: Backup konnte nicht erstellt werden!"
    exit 1
fi