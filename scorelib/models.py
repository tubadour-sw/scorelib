from django.db import models
from django.contrib.auth.models import User

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

# --- User Extension ---

class MusicianProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    instrument_filter = models.CharField(
        max_length=255, 
        help_text="Comma-separated list of allowed instruments (e.g. 'Clarinet, Saxophone')"
    )

    def can_view_part(self, part_name):
        """Checks if the user's filter matches the part name."""
        if not self.instrument_filter:
            return False
        filters = [f.strip().lower() for f in self.instrument_filter.split(',')]
        part_name_lower = part_name.lower()
        return any(f in part_name_lower for f in filters)

    def __str__(self):
        return f"Profile of {self.user.username}"

# --- Music Library ---

class Piece(models.Model):
    title = models.CharField(max_length=200)
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

    def __str__(self):
        return f"{self.title} ({self.composer.name})"

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