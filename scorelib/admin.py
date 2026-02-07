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

from urllib import request
from django.contrib import admin, messages
from django.urls import path, reverse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils.html import format_html  
from django.http import HttpResponseRedirect, HttpResponse
from django import forms
from django.db import models
from django.forms import Textarea
from difflib import SequenceMatcher
import json
import io
import zipfile
import csv
import subprocess
import shutil

# Authentifizierung
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import (
    LoanRecord, Piece, Part, Composer, Arranger, Publisher, InstrumentGroup,
    Genre, Venue, Concert, ProgramItem, AudioRecording, MusicianProfile, 
    SiteSettings, ExternalLink
)
from .forms import PartSplitFormSet
from .utils import process_pdf_split
from .views import piece_csv_import, import_musicians

def find_similar_names(queryset, threshold=0.80):
    """Find similar names and group them into clusters using connectivity.
    
    Returns a list of clusters, where each cluster is a dict with:
    - 'entries': list of dicts with id, name
    - 'min_similarity': the minimum similarity percentage in the cluster
    - 'avg_similarity': the average similarity percentage in the cluster
    """
    items = list(queryset.values_list('id', 'name').order_by('name'))
    
    if len(items) < 2:
        return []
    
    # Build a similarity graph: edges between entries with similarity >= threshold
    similarity_graph = {}  # item_index -> [(item_index, similarity), ...]
    
    for i in range(len(items)):
        similarity_graph[i] = []
    
    for i, (id1, name1) in enumerate(items):
        for j, (id2, name2) in enumerate(items[i+1:], start=i+1):
            norm_name1 = name1.lower().strip()
            norm_name2 = name2.lower().strip()
            
            if norm_name1 == norm_name2:
                continue  # Skip exact duplicates (handle separately)
            
            matcher = SequenceMatcher(None, norm_name1, norm_name2)
            ratio = matcher.ratio()
            
            if ratio >= threshold:
                similarity_graph[i].append((j, ratio))
                similarity_graph[j].append((i, ratio))
    
    # Find connected components (clusters) using DFS
    visited = set()
    clusters = []
    
    def dfs(node, cluster_indices):
        visited.add(node)
        cluster_indices.append(node)
        for neighbor, sim in similarity_graph[node]:
            if neighbor not in visited:
                dfs(neighbor, cluster_indices)
    
    for i in range(len(items)):
        if i not in visited and similarity_graph[i]:  # Only if has connections
            cluster_indices = []
            dfs(i, cluster_indices)
            
            # Convert indices to entries with similarity scores
            cluster_entries = []
            cluster_similarities = []
            
            for idx in cluster_indices:
                cluster_entries.append({
                    'id': items[idx][0],
                    'name': items[idx][1],
                })
                # Get similarity scores for this entry
                for neighbor_idx, sim in similarity_graph[idx]:
                    if neighbor_idx in cluster_indices:
                        cluster_similarities.append(sim)
            
            if cluster_entries:
                avg_sim = sum(cluster_similarities) / len(cluster_similarities) if cluster_similarities else 0
                min_sim = min(cluster_similarities) if cluster_similarities else 0
                
                clusters.append({
                    'entries': sorted(cluster_entries, key=lambda x: x['name'].lower()),
                    'min_similarity': round(min_sim * 100, 1),
                    'avg_similarity': round(avg_sim * 100, 1),
                })
    
    # Sort by average similarity descending
    return sorted(clusters, key=lambda x: x['avg_similarity'], reverse=True)


def get_generic_merge_response(admin_obj, request, queryset, title, action_name):
    """Renders the confirmation template for all models"""
    if queryset.count() < 2:
        admin_obj.message_user(request, "Bitte wählen Sie mindestens zwei Einträge aus.", messages.WARNING)
        return None
        
    return render(request, 'admin/generic_merge_confirmation.html', {
        'title': title,
        'queryset': queryset,
        'master_field_name': 'master_id',
        'action_name': action_name,
    })


@admin.action(description="Ausgewählte Stücke als ZIP herunterladen")
def download_parts_as_zip(modeladmin, request, queryset):
    # Limit in Bytes (z.B. 50 MB)
    MAX_SIZE_MB = 250
    MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024
    
    total_size = 0
     # First check total size of PDFs
    for piece in queryset:
        for part in piece.parts.all():
            if part.pdf_file:
                try:
                    total_size += part.pdf_file.size
                except (FileNotFoundError, AttributeError):
                    continue

    if total_size > MAX_SIZE_BYTES:
        size_actual = total_size / (1024 * 1024)
        modeladmin.message_user(
            request, 
            f"Download abgebrochen: Die Dateien sind insgesamt {size_actual:.1f} MB groß (Limit: {MAX_SIZE_MB} MB). "
            "Bitte wählen Sie weniger Stücke aus.",
            level=messages.ERROR
        )
        return HttpResponseRedirect(request.get_full_path())
    
    buffer = io.BytesIO()
    try:
        with zipfile.ZipFile(buffer, 'w') as zip_file:
            for piece in queryset:
                parts = piece.parts.all()
                for part in parts:
                    if part.pdf_file: 

                        file_path = part.pdf_file.path

                        # Generate filename (clean special characters/spaces)
                        safe_title = "".join(x for x in piece.title if x.isalnum() or x in "._- ")
                        safe_part = "".join(x for x in part.part_name if x.isalnum() or x in "._- ")
                        filename = f"{safe_title}_{safe_part}.pdf"
                        # arcname is name inside ZIP
                        arcname = f"{safe_title}/{filename}".replace(" ", "_")
                        try:
                            zip_file.write(file_path, arcname)
                        except FileNotFoundError:
                            continue
    except Exception as e:
        modeladmin.message_user(request, f"Fehler beim Erstellen der ZIP: {e}", level='ERROR')
        return HttpResponseRedirect(request.get_full_path())
    
    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename="noten_export.zip"'
    return response

@admin.action(description="Ausgewählte Stücke als CSV exportieren")
def export_pieces_csv(modeladmin, request, queryset):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="notenbank_export.csv"'
    
    # utf-8-sig für Excel-Kompatibilität (Umlaute)
    # quoting=csv.QUOTE_MINIMAL sorgt dafür, dass Felder mit Semikolons in " " gesetzt werden
    writer = csv.writer(response, delimiter=';', quoting=csv.QUOTE_MINIMAL)
    
    # Header-Zeile (angepasst an dein Import-Format ohne is_owned_by_orchestra)
    writer.writerow([
        'Label', 'Title', 'Composer', 'Arranger', 'Publisher', 
        'Difficulty', 'Duration', 'Genres', 'Concerts'
    ])
    
    # Queryset optimieren, um Datenbankabfragen in der Schleife zu minimieren (prefetch_related)
    queryset = queryset.prefetch_related('genres', 'concerts')
    
    for piece in queryset:
        # Genres als kommagetrennte Liste
        genres_list = ", ".join([g.name for g in piece.genres.all()])
        
        # Konzerte als kommagetrennte Liste (Titel und Jahr)
        concerts_list = ", ".join([c.title for c in piece.concerts.all()])
        
        writer.writerow([
            piece.archive_label,
            piece.title,
            piece.composer.name if piece.composer else '',
            piece.arranger.name if piece.arranger else '',
            piece.publisher.name if piece.publisher else '',
            piece.difficulty,
            piece.duration,
            genres_list,
            concerts_list
        ])
    
    return response

# --- INLINES ---
# This allows adding Parts directly while editing a Piece
class LoanRecordInline(admin.TabularInline):
    model = LoanRecord
    extra = 0
    classes = ['collapse'] # Makes the entire history collapsible
    verbose_name = "Verleih-Historie"
    fields = ('partner_name', 'loan_date', 'return_date', 'notes')
    formfield_overrides = {
        models.TextField: {
            'widget': Textarea(attrs={
                'rows': 1, 
                'cols': 30, 
                'style': 'height: 2em; min-height: 2em; transition: height 0.2s;'
            })
        },
    }
    

class PartInline(admin.TabularInline):
    model = Part
    extra = 0  # Don't show unnecessary empty rows
    fields = ('part_name', 'pdf_file', 'view_pdf_link')
    readonly_fields = ('view_pdf_link',)

    def view_pdf_link(self, obj):
        if obj.pdf_file:
            return format_html('<a href="{}" target="_blank">📄 Öffnen</a>', obj.pdf_file.url)
        return "-"
    view_pdf_link.short_description = "Vorschau"

# This allows managing the concert program directly within the Concert view
class ProgramItemInline(admin.TabularInline):
    model = ProgramItem
    extra = 3
    autocomplete_fields = ['piece'] # Search for pieces within the concert view

class ExternalLinkInline(admin.TabularInline):
    model = ExternalLink
    extra = 1 

# --- ADMIN CLASSES ---

@admin.register(Composer)
class ComposerAdmin(admin.ModelAdmin):
    search_fields = ['name'] # Required for autocomplete
    list_display = ('name',)
    actions = ['merge_composers_action', 'suggest_merge_composers_action']

    # Example for Composer (Arranger similar)
    def merge_composers_action(self, request, queryset):
        if 'apply' in request.POST:
            master_id = request.POST.get('master_id') # Must match master_field_name
            master = get_object_or_404(Composer, pk=master_id)
            others = queryset.exclude(pk=master.pk)
            
            # Reassign all pieces
            Piece.objects.filter(composer__in=others).update(composer=master)
            others.delete()
            
            self.message_user(request, f"Erfolgreich in {master.name} zusammengeführt.")
            return HttpResponseRedirect(request.get_full_path())
        
        return get_generic_merge_response(self, request, queryset, "Composer mergen", "merge_composers_action")

    merge_composers_action.short_description = "Ausgewählte Composer zusammenführen"
    
    def suggest_merge_composers_action(self, request, queryset):
        """Find and suggest potential duplicate composers based on name similarity."""
        # Redirect to the dedicated suggestions page
        return redirect(reverse('suggest_merges_page', args=['composer']))
    
    suggest_merge_composers_action.short_description = "Mögliche Duplikate vorschlagen"
 

@admin.register(Arranger)
class ArrangerAdmin(admin.ModelAdmin):
    search_fields = ['name'] # Required for autocomplete
    
    list_display = ('name',)
    actions = ['merge_arrangers_action', 'suggest_merge_arrangers_action']

    def merge_arrangers_action(self, request, queryset):
        if 'apply' in request.POST:
            master_id = request.POST.get('master_id') # Must match master_field_name
            master = get_object_or_404(Arranger, pk=master_id)
            others = queryset.exclude(pk=master.pk)
            
            # Reassign all pieces
            Piece.objects.filter(arranger__in=others).update(arranger=master)
            others.delete()
            
            self.message_user(request, f"Erfolgreich in {master.name} zusammengeführt.")
            return HttpResponseRedirect(request.get_full_path())
        
        return get_generic_merge_response(self, request, queryset, "Komponisten mergen", "merge_arrangers_action")

    merge_arrangers_action.short_description = "Ausgewählte Arranger zusammenführen"
    
    def suggest_merge_arrangers_action(self, request, queryset):
        """Find and suggest potential duplicate arrangers based on name similarity."""
        # Redirect to the dedicated suggestions page
        return redirect(reverse('suggest_merges_page', args=['arranger']))
    
    suggest_merge_arrangers_action.short_description = "Mögliche Duplikate vorschlagen"
 

@admin.register(Publisher)
class PublisherAdmin(admin.ModelAdmin):
    search_fields = ['name'] # Required for autocomplete
    
    actions = ['merge_publisher_action', 'suggest_merge_publisher_action']

    # Example for Publisher (Arranger similar)
    def merge_publisher_action(self, request, queryset):
        if 'apply' in request.POST:
            master_id = request.POST.get('master_id') # Must match master_field_name
            master = get_object_or_404(Publisher, pk=master_id)
            others = queryset.exclude(pk=master.pk)
            
            # Reassign all pieces
            Piece.objects.filter(publisher__in=others).update(publisher=master)
            others.delete()
            
            self.message_user(request, f"Erfolgreich in {master.name} zusammengeführt.")
            return HttpResponseRedirect(request.get_full_path())
        
        return get_generic_merge_response(self, request, queryset, "Publisher mergen", "merge_publisher_action")

    merge_publisher_action.short_description = "Ausgewählte Publisher zusammenführen"
    
    def suggest_merge_publisher_action(self, request, queryset):
        """Find and suggest potential duplicate publishers based on name similarity."""
        # Redirect to the dedicated suggestions page
        return redirect(reverse('suggest_merges_page', args=['publisher']))
    
    suggest_merge_publisher_action.short_description = "Mögliche Duplikate vorschlagen"


@admin.register(Piece)
class PieceAdmin(admin.ModelAdmin):
    # Inlines und Auswahl-Hilfen
    inlines = [ExternalLinkInline, LoanRecordInline, PartInline, ]
    filter_horizontal = ('genres',)
    autocomplete_fields = ('composer', 'arranger', 'publisher')
    
    # readonly_fields für den Button
    readonly_fields = ('download_button',)

    # Die neuen Fieldsets für Struktur
    fieldsets = (    
        ('Basis-Informationen', {
            'fields': ('title', 'additional_info', 'archive_label', 'is_owned_by_orchestra')
        }),
        ('Musikalische Details', {
            'fields': ('composer', 'arranger', 'publisher', 'genres', 'is_medley', 'duration', 'difficulty')
        }),
        ('Aktionen', {
            'fields': ('download_button',),
        }),
    )

    # Listenansicht
    list_display = ('title', 'archive_label', 'composer', 'arranger', 'publisher', 'display_genres', 'get_status_display', 'view_parts_link')
    list_filter = ('genres', 'composer', 'arranger', 'difficulty', 'publisher', 'is_owned_by_orchestra')
    search_fields = ('title', 'archive_label', 'composer__name', 'arranger__name', 'additional_info')
    list_editable = ('archive_label',)
    list_display_links = ('title',)
    actions = [download_parts_as_zip, export_pieces_csv]

    def get_status_display(self, obj):
        return obj.current_status['label']
    get_status_display.short_description = "Status"
    
    def display_genres(self, obj):
        # Get all genres of the piece and join them with commas
        return ", ".join([genre.name for genre in obj.genres.all()])
        
    class Media:
        js = ('admin/js/jquery.init.js', 'js/admin_filter_collapse.js')
        css = {
            'all': ('css/admin_custom.css',)
        }
    
    # Heading for the column in admin
    display_genres.short_description = 'Genres'
    
    # We specify that 'title' instead of 'archive_label' is the link
    list_display_links = ('title',)
    
    # Optional: Enables quick editing of the label directly in the list
    list_editable = ('archive_label',) 
    
    search_fields = ('title', 'archive_label', 'composer__name', 'arranger__name', 'additional_info')
    ordering = ('title',)

    def download_button(self, obj):
        if obj.pk:
            url = reverse('admin:piece-download-zip', args=[obj.pk])
            return format_html(
                '<a class="button" href="{}" style="background: #417690; color: white; padding: 10px 15px; border-radius: 4px; text-decoration: none;">'
                '📥 Alle Stimmen als ZIP herunterladen'
                '</a>',
                url
            )
        return "Speichere das Stück zuerst."
    download_button.short_description = "Export PDFs als ZIP"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:piece_id>/change/split/', self.admin_site.admin_view(self.split_view), name='piece-split'),
            path('import-csv/', self.admin_site.admin_view(piece_csv_import), name='piece_csv_import'),
            path('<int:object_id>/download-zip/', self.admin_site.admin_view(self.download_single_piece_zip), name='piece-download-zip'),
        ]
        return custom_urls + urls

    def download_single_piece_zip(self, request, object_id):
        # Nutzt die korrigierte Action für das gefundene Stück
        return download_parts_as_zip(self, request, Piece.objects.filter(pk=object_id))

    def get_status_display(self, obj):
        return obj.current_status['label']
    get_status_display.short_description = "Status"

    def display_genres(self, obj):
        return ", ".join([genre.name for genre in obj.genres.all()])
    display_genres.short_description = 'Genres'

    def view_parts_link(self, obj):
        count = obj.parts.count()
        url = reverse('admin:scorelib_part_changelist') + f'?piece__id__exact={obj.pk}'
        return format_html('<a href="{}">{} Stimmen anzeigen</a>', url, count)
    view_parts_link.short_description = 'Einzelstimmen'

    # The view logic for the split form
    def split_view(self, request, piece_id):
        piece = get_object_or_404(Piece, pk=piece_id)
        existing_part_names = Part.objects.order_by('part_name').values_list('part_name', flat=True).distinct()
        
        if request.method == 'POST':
            formset = PartSplitFormSet(request.POST) #
            master_pdf = request.FILES.get('master_pdf') #
            
            if formset.is_valid() and master_pdf: #
                # BUG FIX: We get data from the validated formset
                # and filter only the rows that are actually filled out.
                valid_data_list = []
                for form_data in formset.cleaned_data:
                    # Check if both name and pages are filled in
                    if form_data.get('part_name') and form_data.get('pages'):
                        valid_data_list.append(form_data)
                
                if not valid_data_list:
                    self.message_user(request, "Bitte geben Sie bei mindestens einer Stimme sowohl den Namen als auch die Seiten an.", messages.WARNING)
                else:
                    try:
                        # IMPORTANT: Pass the filtered list 'valid_data_list' here
                        process_pdf_split(piece, master_pdf, valid_data_list) #
                        self.message_user(request, f"Erfolgreich: Stimmen für '{piece.title}' wurden erstellt.", messages.SUCCESS) #
                        return redirect('admin:scorelib_piece_change', piece.id) #
                    except Exception as e:
                        self.message_user(request, f"Fehler beim Splitten: {str(e)}", messages.ERROR) #
            else:
                self.message_user(request, "Das Formular ist ungültig. Bitte prüfen Sie Ihre Eingaben.", messages.ERROR)
        else:
            formset = PartSplitFormSet() #

        context = {
            **self.admin_site.each_context(request),
            'piece': piece,
            'formset': formset,
            'existing_part_names': existing_part_names,
            'title': f'PDF Splitten: {piece.title}',
            'opts': self.model._meta, # Wichtig für die Admin-Breadcrumbs
        }
        return render(request, 'admin/split_pdf_form.html', context)
    

@admin.register(Concert)
class ConcertAdmin(admin.ModelAdmin):
    list_display = ('title', 'subtitle', 'date', 'venue')
    list_filter = ('date', 'venue')
    search_fields = ['title', 'subtitle']
    autocomplete_fields = ('venue',)  # Enable searchable venue dropdown
    inlines = [ProgramItemInline]
    readonly_fields = ('rip_audio_link',)
    actions = ['merge_concerts_action']

    fieldsets = (
        (None, {
            'fields': ('title', 'subtitle', 'date', 'venue', 'poster')
        }),
        ('Audio-Verarbeitung', {
            'fields': ('rip_audio_link',),
            'description': 'Hier können Sie Audio-Aufnahmen für dieses Konzert verarbeiten.'
        }),
    )

    def merge_concerts_action(self, request, queryset):
        if 'apply' in request.POST:
            master_id = request.POST.get('master_id')
            master = get_object_or_404(Concert, pk=master_id)
            others = queryset.exclude(pk=master.pk)

            for other in others:
                # Add program items to the end of the master concert
                current_max_order = master.programitem_set.count()
                for item in other.programitem_set.all():
                    current_max_order += 1
                    item.concert = master
                    item.order = current_max_order
                    item.save()
                other.delete()

            self.message_user(request, "Konzerte erfolgreich zusammengeführt.")
            return HttpResponseRedirect(request.get_full_path())

        return get_generic_merge_response(self, request, queryset, "Konzerte mergen", "merge_concerts_action")
 
    merge_concerts_action.short_description = "Ausgewählte Concerts zusammenführen"

    def rip_audio_link(self, obj):
        if not obj.pk: return "-" # in case the concert is not saved yet
        
        settings = SiteSettings.get_solo() 
        
        if settings and settings.audio_ripping_enabled:
            url = reverse('audio_ripping_page', args=[obj.pk])
            return format_html(
                '<a class="button" href="{}" style="background-color: #417690; color: white;">'
                '💿 CD-Tracks für dieses Konzert hochladen</a>', 
                url
            )
        return "Feature in den Site-Settings deaktiviert oder ffmpeg fehlt."
    
    rip_audio_link.short_description = "Audio-Verarbeitung"
   
@admin.register(InstrumentGroup)
class InstrumentGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'filter_strings')

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            # The URL is now under /admin/scorelib/instrumentgroup/unmatched-parts/
            path('unmatched-parts/', self.admin_site.admin_view(self.unmatched_parts_view), name='unmatched-parts'),
        ]
        return custom_urls + urls

    def unmatched_parts_view(self, request):
        all_parts = Part.objects.select_related('piece').all()
        # We use the optimized logic via the groups
        all_groups = InstrumentGroup.objects.all()
        
        unmatched = []
        for part in all_parts:
            if not any(group.matches_part(part.part_name) for group in all_groups):
                unmatched.append(part)

        context = {
            **self.admin_site.each_context(request),
            'title': 'Verwaiste Stimmen (Keine Gruppe passt)',
            'unmatched_parts': unmatched,
            'opts': self.model._meta, # Important for breadcrumbs and design
        }
        return render(request, 'admin/unmatched_parts.html', context)

    
@admin.register(MusicianProfile)
class MusicianProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'display_groups', 'has_full_archive_access')
    list_editable = ('has_full_archive_access',)
    filter_horizontal = ('instrument_groups',) # Convenient selection widget
    search_fields = ('user_username', 'display_groups')

    def display_groups(self, obj):
        return ", ".join([g.name for g in obj.instrument_groups.all()])
        
    display_groups.short_description = 'Instrumente'
    
# --- User & Profile Integration ---

class MusicianProfileInline(admin.StackedInline):
    model = MusicianProfile
    can_delete = False
    verbose_name_plural = 'Musician Profile / Instrument Filter'
    fk_name = 'user'

class UserAdmin(BaseUserAdmin):
    inlines = (MusicianProfileInline, )
    
    # Register the custom template for the import button
    change_list_template = "admin/user_changelist_custom.html"
    
    # Optional: Extend columns in the user overview
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_instruments', 'is_staff', 'is_active',)
    list_editable = ('is_active',)
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import-user-csv/', self.admin_site.admin_view(import_musicians), name="import_musicians"),
        ]
        return custom_urls + urls
    
    # This method ensures that inlines are ignored when CREATING
    # (add_view) to avoid signal conflicts
    def get_inline_instances(self, request, obj=None):
        if not obj:
            return list()
        return super().get_inline_instances(request, obj)

    def get_instruments(self, obj):
        # Check if the profile exists and return the group names
        if hasattr(obj, 'profile'):
            return ", ".join([g.name for g in obj.profile.instrument_groups.all()])
        return "-"
        
    get_instruments.short_description = 'Instrumente' # Titel der Spalte

@admin.register(Part)
class PartAdmin(admin.ModelAdmin):
    list_display = ('part_name', 'piece', 'pdf_file')
    list_filter = ('piece',)
    search_fields = ('part_name', 'piece__title')
    
# In scorelib/admin.py

@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    search_fields = ['name'] # Required for autocomplete
    list_display = ('name',)
    actions = ['merge_genres_action']

    def merge_genres_action(self, request, queryset):
        if 'apply' in request.POST:
            master_id = request.POST.get('master_id')
            master = get_object_or_404(Genre, pk=master_id)
            others = queryset.exclude(pk=master.pk)

            for other in others:
                for piece in other.piece_set.all():
                    piece.genres.add(master)
                other.delete()

            self.message_user(request, f"Genres in '{master.name}' zusammengeführt.")
            return HttpResponseRedirect(request.get_full_path())

        return get_generic_merge_response(self, request, queryset, "Genres mergen", "merge_genres_action")

    merge_genres_action.short_description = "Ausgewählte Genres verschmelzen"
 
@admin.register(AudioRecording)
class AudioRecordingAdmin(admin.ModelAdmin):
    list_display = ('piece', 'concert', 'audio_file')

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        
        concert_id = None
        # 1. GET parameter takes priority (for JS reload)
        if 'concert' in request.GET:
            concert_id = request.GET.get('concert')
            # Set the field in the form to the value from the URL
            form.base_fields['concert'].initial = concert_id
        # 2. Existing object
        elif obj and obj.concert:
            concert_id = obj.concert.id
        # 3. POST data
        elif request.method == 'POST':
            concert_id = request.POST.get('concert')

        if concert_id:
            # Filter pieces based on ProgramItems
            form.base_fields['piece'].queryset = Piece.objects.filter(
                programitem__concert_id=concert_id
            ).distinct()
        else:
            form.base_fields['piece'].queryset = Piece.objects.none()

        return form
        
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "concert": # Name of the field in AudioRecording
            kwargs["queryset"] = Concert.objects.order_by('title')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    class Media:
        js = ('admin/js/jquery.init.js', 'js/audio_recording_helper.js')

class CurrentLoanFilter(admin.SimpleListFilter):
    title = 'Aktueller Status'
    parameter_name = 'is_active'

    def lookups(self, request, model_admin):
        return (
            ('active', 'Nur laufende Vorgänge'),
            ('closed', 'Abgeschlossen'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'active':
            return queryset.filter(return_date__isnull=True)
        if self.value() == 'closed':
            return queryset.filter(return_date__isnull=False)
            
@admin.register(LoanRecord)
class LoanRecordAdmin(admin.ModelAdmin):
    # Which columns should appear in the overview?
    list_display = ('piece_link', 'get_type', 'partner_name', 'loan_date', 'return_date', 'is_active_badge')
    
    # Filters on the right side
    list_filter = ('piece__is_owned_by_orchestra', 'loan_date', 'return_date', CurrentLoanFilter)
    
    # Search for piece or partner
    search_fields = ('piece__title', 'partner_name', 'notes')

    def get_type(self, obj):
        """Distinguishes visually between 'Loan out' and 'Loan in'"""
        if obj.piece.is_owned_by_orchestra:
            return format_html('<span style="color: #d63384;">↗ Verleih</span>') # Wir geben weg
        return format_html('<span style="color: #0dcaf0;">↘ Fremd-Leihgabe</span>') # Wir holen her
    get_type.short_description = "Art"

    def is_active_badge(self, obj):
        """Shows a colored label whether the transaction is still ongoing"""
        if obj.return_date is None:
            return format_html('<span style="background: #ffc107; color: #000; padding: 2px 8px; border-radius: 10px;">AKTUELL</span>')
        return format_html('<span style="color: #6c757d;">Abgeschlossen</span>')
    is_active_badge.short_description = "Status"

    def piece_link(self, obj):
        url = reverse("admin:scorelib_piece_change", args=[obj.piece.id])
        return format_html('<strong><a href="{}">{}</a></strong>', url, obj.piece)
    
    piece_link.short_description = "Piece"

    
# Remove default User admin and register with our extension
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

# Standard registration for simple models
@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    search_fields = ['name']  # Enable autocomplete search
    list_display = ('name', 'address')


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ('site_title', 'audio_ripping_enabled')
    readonly_fields = ('ffmpeg_status_display',)

    fieldsets = (
        (None, {'fields': ('site_title', 'band_name', 'legal_text')}),
        ('Audio-Ripping', {'fields': ('audio_ripping_enabled', 'ffmpeg_status_display')}),
    )

    def has_add_permission(self, request):
        # Allow adding only if there's no settings instance yet
        return SiteSettings.objects.count() == 0

    def changelist_view(self, request, extra_context=None):
        # Redirect list view to change view of the singleton instance
        obj = SiteSettings.get_solo()
        # Use the admin URL name to avoid duplicating app labels in the path
        url = reverse('admin:scorelib_sitesettings_change', args=[obj.pk])
        return redirect(url)

    def ffmpeg_status_display(self, obj):
        ffmpeg_path = shutil.which('ffmpeg')
        if ffmpeg_path:
            return format_html('<span style="color: green;">✔ ffmpeg gefunden: {}</span>', ffmpeg_path)
        return format_html('<span style="color: red;">✘ ffmpeg nicht im Systempfad gefunden.</span>')
    
    ffmpeg_status_display.short_description = "System-Check"

    # Avoid manual enabling if ffmpeg is not available
    def save_model(self, request, obj, form, change):
        if obj.audio_ripping_enabled and not shutil.which('ffmpeg'):
            obj.audio_ripping_enabled = False
            messages.error(request, "Feature konnte nicht aktiviert werden: ffmpeg wurde auf diesem Server nicht gefunden.")
        super().save_model(request, obj, form, change)
