from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import fnmatch

# --- Core Data (Stammdaten) ---

class Genre(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class Venue(models.Model):
    name = models.CharField(max_length=200, unique=True)
    address = models.TextField(blank=True)

    def __str__(self):
        return self.name

# --- Normalized Entities ---

class Composer(models.Model):
    name = models.CharField(max_length=200, unique=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

class Arranger(models.Model):
    name = models.CharField(max_length=200, unique=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

class Publisher(models.Model):
    name = models.CharField(max_length=200, unique=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

class InstrumentGroup(models.Model):
    name = models.CharField(max_length=100, unique=True, help_text="z.B. Trompete")
    filter_strings = models.CharField(
        max_length=500, 
        help_text="Komma-getrennte Liste (z.B. Trompete*, Flügelhorn*, Cornet*)"
    )

    def __str__(self):
        return self.name
        
    def matches_part(self, part_name):
        """Prüft, ob der Part-Name zu den Filtern dieser Gruppe passt."""
        if not self.filter_strings:
            return False
        
        part_name_lower = part_name.strip().lower()
        filters = [f.strip().lower() for f in self.filter_strings.split(',') if f.strip()]
        
        return any(fnmatch.fnmatch(part_name_lower, f) for f in filters)

class MusicianProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    instrument_groups = models.ManyToManyField(InstrumentGroup, blank=True)
    has_full_archive_access = models.BooleanField(
        default=False, 
        verbose_name="Vollzugriff auf Archiv"
    )

    def can_view_part(self, part_name):
        """Prüft, ob irgendeine der zugeordneten Gruppen den Part matcht."""
        return any(group.matches_part(part_name) for group in self.instrument_groups.all())
        
    def __str__(self):
        return f"Profile of {self.user.username}"

# --- Music Library ---

class Piece(models.Model):
    title = models.CharField(max_length=200)
    additional_info = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="Zusatzinfos / Sätze / Alternativtitel",
        help_text="Hier kannst du Sätze (z.B. 1. Allegro) oder alternative Titel eintragen."
    )
    composer = models.ForeignKey(Composer, on_delete=models.PROTECT, related_name='pieces')
    arranger = models.ForeignKey(Arranger, on_delete=models.SET_NULL, null=True, blank=True, related_name='pieces')
    publisher = models.ForeignKey(Publisher, on_delete=models.SET_NULL, null=True, blank=True, related_name='pieces')
    archive_label = models.CharField(
        max_length=50, 
        blank=True, 
        null=True, 
        verbose_name="Archiv-Label"
    )
    is_medley = models.BooleanField(default=False)
    genres = models.ManyToManyField(Genre, blank=True)
    duration = models.DurationField(
        blank=True, 
        null=True, 
        verbose_name="Dauer"
    )
    difficulty = models.IntegerField(
        blank=True, 
        null=True, 
        verbose_name="Schwierigkeit"
    )
    
    def is_active_for_download(self):
        """
        Prüft, ob das Stück für normale Musiker zum Download verfügbar sein soll.
        Ein Stück ist aktiv, wenn es mit einem Konzert verknüpft ist, 
        das in der Zukunft liegt oder vor weniger als 14 Tagen stattfand.
        """
        grace_period = 14 # in days
        deadline = timezone.now().date() - timedelta(days=grace_period)
        
        # Prüfe, ob es ein verknüpftes Konzert gibt, das nach dem Stichtag liegt
        return self.concerts.filter(date__gte=deadline).exists()

    def __str__(self):
        artists = []
        if self.composer and self.composer.name:
            artists.append(f"{self.composer.name}")
        if self.arranger and self.arranger.name:
            artists.append(f"Arr. {self.arranger.name}")
        return f"{self.title} ({', '.join(artists)})"

class Part(models.Model):
    piece = models.ForeignKey(Piece, on_delete=models.CASCADE, related_name='parts')
    part_name = models.CharField(max_length=100)
    pdf_file = models.FileField(upload_to='sheet_music/parts/')

    def __str__(self):
        return f"{self.part_name} - {self.piece.title}"

# --- Concert Management ---

class Concert(models.Model):
    title = models.CharField(max_length=200)
    subtitle = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        verbose_name="Untertitel"
    )
    date = models.DateTimeField(blank=True, null=True)
    venue = models.ForeignKey(Venue, on_delete=models.SET_NULL, null=True)
    poster = models.ImageField(upload_to='concerts/posters/', blank=True, null=True)
    program = models.ManyToManyField(Piece, through='ProgramItem', related_name='concerts')

    def __str__(self):
        date_txt = f"({self.date.date()})" if self.date else ""
        if self.subtitle:
            return f"{self.title} – {self.subtitle} {date_txt}"
        return f"{self.title} {date_txt}"

class ProgramItem(models.Model):
    concert = models.ForeignKey(Concert, on_delete=models.CASCADE)
    piece = models.ForeignKey(Piece, on_delete=models.CASCADE)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

class AudioRecording(models.Model):
    concert = models.ForeignKey(Concert, on_delete=models.CASCADE, related_name='recordings')
    piece = models.ForeignKey(Piece, on_delete=models.CASCADE)
    audio_file = models.FileField(upload_to='concerts/audio/')
    description = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"{self.piece.title} @ {self.concert.title}"