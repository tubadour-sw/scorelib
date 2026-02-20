"""
SKG Notenbank - Sheet Music Database and Archive Management System
Copyright (C) 2026 Arno Euteneuer

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import smtplib
import os
from email.message import EmailMessage
import sys
from pathlib import Path


# Wir versuchen, die .env Datei manuell zu laden, falls python-dotenv nicht installiert ist
def load_env():
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.strip() and not line.startswith("#"):
                key, value = line.strip().split("=", 1)
                os.environ[key] = value


load_env()

# KONFIGURATION aus Umgebungsvariablen
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
RECIPIENT = os.getenv("SMTP_RECIPIENT")


def send_mail(subject, body):
    if not all([SMTP_SERVER, SMTP_USER, SMTP_PASS]):
        print("Fehler: SMTP-Zugangsdaten unvollständig (Prüfe .env Datei)")
        return

    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = RECIPIENT

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
            print("E-Mail erfolgreich versendet.")
    except Exception as e:
        print(f"Fehler beim Mail-Versand: {e}")


if __name__ == "__main__":
    sub = sys.argv[1] if len(sys.argv) > 1 else "Backup Info"
    msg_body = sys.argv[2] if len(sys.argv) > 2 else ""
    send_mail(sub, msg_body)
