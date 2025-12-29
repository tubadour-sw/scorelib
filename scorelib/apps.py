from django.apps import AppConfig

class LibraryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'scorelib'

    def ready(self):
        # Das Importieren der Signale hier ist wichtig, 
        # damit sie beim Start der App registriert werden.
        import scorelib.signals