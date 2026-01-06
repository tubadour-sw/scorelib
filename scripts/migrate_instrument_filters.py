import os
import django

# Django-Umgebung laden
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'skg_notenbank.settings')
django.setup()

from scorelib.models import MusicianProfile, InstrumentGroup

def run_migration():
    profiles = MusicianProfile.objects.all()
    print(f"Starte Migration für {profiles.count()} Profile...")

    for profile in profiles:
        # 1. Hol den alten String (falls noch vorhanden)
        # Wir nutzen hasattr, falls du das Feld schon gelöscht hast
        old_filters = getattr(profile, 'instrument_filter', None)
        
        if not old_filters:
            print(f"kein Filter vorhanden")
            continue
        
        print(f"Filter gefunden:{old_filters}")
        # 2. Erstelle oder finde eine Gruppe für diesen exakten Filter-String
        # Alternativ: Hier könnte man den String splitten und Einzelgruppen anlegen
        group_name = old_filters.split(',')[0].strip().replace('*', '')
        
        group, created = InstrumentGroup.objects.get_or_create(
            filter_strings=old_filters,
            defaults={'name': f"Gruppe {group_name}"}
        )
        
        # 3. Verknüpfung setzen
        profile.instrument_groups.add(group)
        print(f"Profil {profile.user.username}: Zugeordnet zu Gruppe '{group.name}'")

    print("Migration abgeschlossen!")

if __name__ == "__main__":
    run_migration()