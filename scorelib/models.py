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

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import timedelta
import fnmatch

# --- Core Data ---

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
        """Check if the part name matches this group's filter patterns."""
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
        """Check if any assigned instrument group matches this part."""
        return any(group.matches_part(part_name) for group in self.instrument_groups.all())
        
    def __str__(self):
        return f"Profile of {self.user.username}"


class SiteSettings(models.Model):
    """Singleton model to store site-specific settings editable in the admin.

    Use this model to configure values that differ per orchestra/band,
    such as the site title, favicon and the legal/imprint text.
    """
    site_title = models.CharField(max_length=200, default='SKG Notenbank')
    favicon = models.ImageField(upload_to='site/', blank=True, null=True)
    legal_text = models.TextField(blank=True, null=True, help_text='HTML or plain-text legal / imprint content')

    class Meta:
        verbose_name = 'Site Settings'

    def __str__(self):
        return 'Site Settings'

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

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
    is_owned_by_orchestra = models.BooleanField(
        default=True, 
        verbose_name="Eigentum",
        help_text="Haken weg, wenn wir das Stück von jemand anderem geliehen haben."
    )

    @property
    def current_status(self):
        """
        Determine the current status of the piece.
        Returns a dictionary with status code, label, and availability flag.
        """
        today = timezone.now().date()
        active_loan = self.loan_records.filter(
            loan_date__lte=today
        ).filter(
            models.Q(return_date__isnull=True) | models.Q(return_date__gte=today)
        ).first()
        
        if self.is_owned_by_orchestra:
            if active_loan:
                return {'code': 'OUT', 'label': f'Eigentum (Verliehen an {active_loan.partner_name})', 'available': False}
            return {'code': 'IN', 'label': 'Eigentum (verfügbar)', 'available': True}
        else:
            if active_loan:
                return {'code': 'BORROWED', 'label': f'Leihgabe (geliehen von {active_loan.partner_name})', 'available': True}
            return {'code': 'RETURNED', 'label': 'Leihgabe (aktuell zurückgegeben)', 'available': False}
    
    def is_active_for_download(self):
        """
        Check if the piece should be available for download to regular musicians.
        A piece is active if it is linked to a concert that is in the future
        or took place less than 14 days ago.
        """
        grace_period = 14  # in days
        deadline = timezone.now().date() - timedelta(days=grace_period)
        
        # Check if there is a linked concert that is after the deadline
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

class LoanRecord(models.Model):
    piece = models.ForeignKey(Piece, on_delete=models.CASCADE, related_name='loan_records')
    partner_name = models.CharField(max_length=200, verbose_name="Partner (Verein/Person/Verlag)")
    loan_date = models.DateField(default=timezone.now, verbose_name="Datum (Erhalt/Gabe)")
    return_date = models.DateField(null=True, blank=True, verbose_name="Rückgabedatum")
    notes = models.TextField(blank=True, null=True, verbose_name="Bemerkungen")

    def clean(self):
        # Check for overlapping loan periods for the same piece
        overlapping = LoanRecord.objects.filter(
            piece=self.piece,
            loan_date__lte=self.return_date if self.return_date else timezone.now().date() + timedelta(days=3650),
            return_date__gte=self.loan_date
        ).exclude(pk=self.pk)
        
        if overlapping.exists():
            raise ValidationError("Achtung: Dieser Zeitraum überschneidet sich mit einer anderen Buchung für dieses Stück!")

    class Meta:
        ordering = ['-loan_date']
        verbose_name = "Loan History"

    def __str__(self):
        return f"{self.piece.title} - {self.partner_name} ({self.loan_date})"

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