#!/bin/bash

# Pfade definieren
# Ermittelt das Verzeichnis, in dem dieses Skript liegt
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
PROJECT_DIR=$(dirname "$SCRIPT_DIR")
DB_FILE="$PROJECT_DIR/db.sqlite3"
MEDIA_DIR="$PROJECT_DIR/media"
BACKUP_DIR="$PROJECT_DIR/backups"
STATE_FILE="$BACKUP_DIR/.last_state"
MAIL_SCRIPT="$SCRIPT_DIR/send_backup_mail.py"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="full_backup_$TIMESTAMP.tar.gz"

mkdir -p "$BACKUP_DIR"

# 1. Fingerabdruck berechnen (DB und Media-Dateien)
CURRENT_STATE=$(find "$MEDIA_DIR" "$DB_FILE" -type f -printf '%T@ %s %p\n' | md5sum)

# 2. Prüfen, ob sich etwas geändert hat
if [ -f "$STATE_FILE" ]; then
    LAST_STATE=$(cat "$STATE_FILE")
    if [ "$CURRENT_STATE" == "$LAST_STATE" ]; then
        # Keine Mail bei "Nichts getan", um Spam zu vermeiden
        exit 0
    fi
fi

# 3. Backup-Vorgang
TEMP_DB="/tmp/temp_db.sqlite3"
sqlite3 "$DB_FILE" ".backup '$TEMP_DB'"

# Archiv erstellen (enthält media/ und die Datenbank)
tar -czf "$BACKUP_DIR/$BACKUP_NAME" -C "$PROJECT_DIR" media -C "/tmp" temp_db.sqlite3
rm "$TEMP_DB"

# 4. Rotation: Behalte nur die letzten 10
cd "$BACKUP_DIR" && ls -t full_backup_*.tar.gz | tail -n +11 | xargs -r rm

# 5. Status speichern
echo "$CURRENT_STATE" > "$STATE_FILE"

# 6. E-Mail Benachrichtigung
FILE_SIZE=$(du -h "$BACKUP_DIR/$BACKUP_NAME" | cut -f1)
MAIL_SUBJECT="✅ Backup SKG Notenbank erstellt"
MAIL_BODY="Ein neues Backup wurde erstellt, da Änderungen an der Datenbank oder den Dateien erkannt wurden.

Datei: $BACKUP_NAME
Größe: $FILE_SIZE
Zeitpunkt: $(date)

Es werden weiterhin die letzten 10 Backups im Verzeichnis aufbewahrt."

python3 "$MAIL_SCRIPT" "$MAIL_SUBJECT" "$MAIL_BODY"