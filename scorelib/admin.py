from django.contrib import admin, messages
from django.urls import path, reverse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils.html import format_html  
from django.http import HttpResponseRedirect

# Authentifizierung
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

# Deine Modelle und Tools
from .models import (
    Piece, Part, Composer, Arranger, Publisher, 
    Genre, Venue, Concert, ProgramItem, AudioRecording, MusicianProfile
)
from .forms import PartSplitFormSet
from .utils import process_pdf_split
from .views import piece_csv_import

def get_generic_merge_response(admin_obj, request, queryset, title, action_name):
    """ Rendert das Bestätigungs-Template für alle Models """
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

class PartInline(admin.TabularInline):
    model = Part
    extra = 0  # Auf 0 setzen, damit nicht unnötig leere Zeilen erscheinen
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

    # Beispiel für Composer (Arranger analog)
    def merge_composers_action(self, request, queryset):
        if 'apply' in request.POST:
            master_id = request.POST.get('master_id') # Muss mit master_field_name übereinstimmen
            master = get_object_or_404(Composer, pk=master_id)
            others = queryset.exclude(pk=master.pk)
            
            # Alle Stücke umhängen
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
            master_id = request.POST.get('master_id') # Muss mit master_field_name übereinstimmen
            master = get_object_or_404(Arranger, pk=master_id)
            others = queryset.exclude(pk=master.pk)
            
            # Alle Stücke umhängen
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

    # Beispiel für Publisher (Arranger analog)
    def merge_publisher_action(self, request, queryset):
        if 'apply' in request.POST:
            master_id = request.POST.get('master_id') # Muss mit master_field_name übereinstimmen
            master = get_object_or_404(Publisher, pk=master_id)
            others = queryset.exclude(pk=master.pk)
            
            # Alle Stücke umhängen
            Piece.objects.filter(publisher__in=others).update(publisher=master)
            others.delete()
            
            self.message_user(request, f"Erfolgreich in {master.name} zusammengeführt.")
            return HttpResponseRedirect(request.get_full_path())
        
        return get_generic_merge_response(self, request, queryset, "Publisher mergen", "merge_publisher_action")

        merge_publisher_action.short_description = "Ausgewählte Publisher zusammenführen"


@admin.register(Piece)
class PieceAdmin(admin.ModelAdmin):
    inlines = [PartInline]
    filter_horizontal = ('genres',)
    # Wir definieren die Spalten
    list_display = ('title', 'archive_label', 'composer', 'arranger', 'publisher', 'display_genres', 'difficulty', 'duration', 'view_parts_link')
    
    # Erlaube das Filtern nach Schwierigkeit direkt in der rechten Seitenleiste
    list_filter = ('genres', 'composer', 'arranger', 'difficulty', 'publisher')
    
    def display_genres(self, obj):
        # Holt alle Genres des Stücks und verbindet sie mit Komma
        return ", ".join([genre.name for genre in obj.genres.all()])
        
    class Media:
        # Hier definieren wir CSS, das nur für diesen Admin-Bereich geladen wird
        css = {
            'all': ('css/admin_custom.css',)
        }
    
    # Überschrift für die Spalte im Admin
    display_genres.short_description = 'Genres'
    
    # Wir legen fest, dass 'title' statt 'archive_label' der Link ist
    list_display_links = ('title',)
    
    # Optional: Ermöglicht das schnelle Editieren des Labels direkt in der Liste
    list_editable = ('archive_label',) 
    
    search_fields = ('title', 'archive_label', 'composer__name', 'arranger__name')
    ordering = ('title',)

    # 2. Registrierung der speziellen Split-URL
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

    # 3. Der Button in der Listenansicht
    def split_pdf_button(self, obj):
        url = reverse('admin:piece-split', args=[obj.pk])
        return format_html(
            '<a class="button" href="{}" style="background-color: #417690; color: white;">PDF Splitten</a>',
            url
        )
    split_pdf_button.short_description = 'Aktionen'

    # 4. Ein Link, um direkt zu den Einzelstimmen zu springen
    def view_parts_link(self, obj):
        count = obj.parts.count()
        url = reverse('admin:scorelib_part_changelist') + f'?piece__id__exact={obj.pk}'
        return format_html('<a href="{}">{} Stimmen anzeigen</a>', url, count)
    view_parts_link.short_description = 'Einzelstimmen'

    # 5. Die View-Logik für das Splitting-Formular
    def split_view(self, request, piece_id):
        piece = get_object_or_404(Piece, pk=piece_id)
        existing_part_names = Part.objects.order_by('part_name').values_list('part_name', flat=True).distinct()
        
        if request.method == 'POST':
            formset = PartSplitFormSet(request.POST) #
            master_pdf = request.FILES.get('master_pdf') #
            
            if formset.is_valid() and master_pdf: #
                # FEHLERBEHEBUNG: Wir holen die Daten aus dem validierten Formset
                # und filtern nur die Zeilen heraus, die wirklich ausgefüllt sind.
                valid_data_list = []
                for form_data in formset.cleaned_data:
                    # Wir prüfen, ob sowohl der Name als auch die Seiten ausgefüllt sind
                    if form_data.get('part_name') and form_data.get('pages'):
                        valid_data_list.append(form_data)
                
                if not valid_data_list:
                    self.message_user(request, "Bitte geben Sie bei mindestens einer Stimme sowohl den Namen als auch die Seiten an.", messages.WARNING)
                else:
                    try:
                        # WICHTIG: Übergib hier die gefilterte Liste 'valid_data_list'
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
    list_display = ('title', 'date', 'venue')
    list_filter = ('date', 'venue')
    inlines = [ProgramItemInline]
    
    actions = ['merge_concerts_action']

    def merge_concerts_action(self, request, queryset):
        if 'apply' in request.POST:
            master_id = request.POST.get('master_id')
            master = get_object_or_404(Concert, pk=master_id)
            others = queryset.exclude(pk=master.pk)

            for other in others:
                # Setliste ans Ende des Master-Konzerts hängen
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

@admin.register(MusicianProfile)
class MusicianProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'instrument_filter')
    search_fields = ('user__username', 'instrument_filter')

# --- User & Profile Integration ---

class MusicianProfileInline(admin.StackedInline):
    model = MusicianProfile
    can_delete = False
    verbose_name_plural = 'Musician Profile / Instrument Filter'
    fk_name = 'user'

class UserAdmin(BaseUserAdmin):
    inlines = (MusicianProfileInline, )
    
    # Optional: Spalten in der Benutzerübersicht erweitern
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_instruments', 'is_staff')
    
    # Diese Methode sorgt dafür, dass Inlines beim ERSTELLEN 
    # (add_view) ignoriert werden, um den Signal-Konflikt zu vermeiden
    def get_inline_instances(self, request, obj=None):
        if not obj:
            return list()
        return super().get_inline_instances(request, obj)

    def get_instruments(self, obj):
        return obj.profile.instrument_filter if hasattr(obj, 'profile') else "-"
    get_instruments.short_description = 'Instruments'

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
        # 1. GET-Parameter hat Vorrang (für den JS-Reload)
        if 'concert' in request.GET:
            concert_id = request.GET.get('concert')
            # Setze das Feld im Formular auf den Wert aus der URL
            form.base_fields['concert'].initial = concert_id
        # 2. Bestehendes Objekt
        elif obj and obj.concert:
            concert_id = obj.concert.id
        # 3. POST-Daten
        elif request.method == 'POST':
            concert_id = request.POST.get('concert')

        if concert_id:
            # Filterung der Stücke basierend auf ProgramItems
            form.base_fields['piece'].queryset = Piece.objects.filter(
                programitem__concert_id=concert_id
            ).distinct()
        else:
            form.base_fields['piece'].queryset = Piece.objects.none()

        return form

    class Media:
        js = ('admin/js/jquery.init.js', 'js/audio_recording_helper.js')
    
# Standard User-Admin entfernen und mit unserer Erweiterung neu setzen
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

# Standard registration for simple models
admin.site.register(Venue)
