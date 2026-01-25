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

from django.contrib import admin, messages
from django.urls import path, reverse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils.html import format_html  
from django.http import HttpResponseRedirect
from django import forms
from django.db import models
from django.forms import Textarea

# Authentifizierung
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

# Deine Modelle und Tools
from .models import (
    LoanRecord, Piece, Part, Composer, Arranger, Publisher, InstrumentGroup,
    Genre, Venue, Concert, ProgramItem, AudioRecording, MusicianProfile, SiteSettings
)
from .forms import PartSplitFormSet
from .utils import process_pdf_split
from .views import piece_csv_import, import_musicians

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

# --- ADMIN CLASSES ---

@admin.register(Composer)
class ComposerAdmin(admin.ModelAdmin):
    search_fields = ['name'] # Required for autocomplete
    list_display = ('name',)
    actions = ['merge_composers_action']

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
 

@admin.register(Arranger)
class ArrangerAdmin(admin.ModelAdmin):
    search_fields = ['name'] # Required for autocomplete
    
    list_display = ('name',)
    actions = ['merge_arrangers_action']

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
 

@admin.register(Publisher)
class PublisherAdmin(admin.ModelAdmin):
    search_fields = ['name'] # Required for autocomplete
    
    actions = ['merge_publisher_action']

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


@admin.register(Piece)
class PieceAdmin(admin.ModelAdmin):
    inlines = [LoanRecordInline, PartInline]
    filter_horizontal = ('genres',)
    autocomplete_fields = ('composer', 'arranger', 'publisher')  # Enable searchable dropdowns
    # Define the columns
    list_display = ('title', 'archive_label', 'composer', 'arranger', 'publisher', 'display_genres', 'get_status_display', 'view_parts_link')
    
    # Allow filtering by difficulty directly in the right sidebar
    list_filter = ('genres', 'composer', 'arranger', 'difficulty', 'publisher', 'is_owned_by_orchestra')

    formfield_overrides = {
        models.TextField: {'widget': forms.Textarea(attrs={'rows': 4, 'cols': 40})},
    } 

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

    # Register the special split URL
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:piece_id>/change/split/',
                self.admin_site.admin_view(self.split_view),
                name='piece-split',
            ),
            path('import-csv/', self.admin_site.admin_view(piece_csv_import), name='piece_csv_import'),
        ]
        return custom_urls + urls

    # Button in the list view
    def split_pdf_button(self, obj):
        url = reverse('admin:piece-split', args=[obj.pk])
        return format_html(
            '<a class="button" href="{}" style="background-color: #417690; color: white;">PDF Splitten</a>',
            url
        )
    split_pdf_button.short_description = 'Aktionen'

    # A link to jump directly to individual parts
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
    
    actions = ['merge_concerts_action']

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
    list_display = ('site_title',)

    def has_add_permission(self, request):
        # Allow adding only if there's no settings instance yet
        return SiteSettings.objects.count() == 0

    def changelist_view(self, request, extra_context=None):
        # Redirect list view to change view of the singleton instance
        obj = SiteSettings.get_solo()
        # Use the admin URL name to avoid duplicating app labels in the path
        url = reverse('admin:scorelib_sitesettings_change', args=[obj.pk])
        return redirect(url)
