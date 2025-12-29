from django.contrib import admin
from django.urls import path, reverse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils.html import format_html  # <-- Das hat gefehlt!

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


# --- INLINES ---
# This allows adding Parts directly while editing a Piece
class PartInline(admin.TabularInline):
    model = Part
    extra = 1 # Number of empty slots for new uploads

# This allows managing the concert program directly within the Concert view
class ProgramItemInline(admin.TabularInline):
    model = ProgramItem
    extra = 3
    autocomplete_fields = ['piece'] # Search for pieces within the concert view

# --- ADMIN CLASSES ---

@admin.register(Composer)
class ComposerAdmin(admin.ModelAdmin):
    search_fields = ['name'] # Required for autocomplete

@admin.register(Arranger)
class ArrangerAdmin(admin.ModelAdmin):
    search_fields = ['name'] # Required for autocomplete

@admin.register(Publisher)
class PublisherAdmin(admin.ModelAdmin):
    search_fields = ['name'] # Required for autocomplete


@admin.register(Piece)
class PieceAdmin(admin.ModelAdmin):
    # Wir definieren die Spalten
    list_display = ('title', 'archive_label', 'composer', 'arranger', 'view_parts_link')
    
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
        # Alle bisherigen Stimmbezeichnungen für das Autocomplete sammeln
        existing_part_names = Part.objects.order_by('part_name').values_list('part_name', flat=True).distinct()
        
        if request.method == 'POST':
            formset = PartSplitFormSet(request.POST)
            master_pdf = request.FILES.get('master_pdf')
            
            if formset.is_valid() and master_pdf:
                try:
                    process_pdf_split(piece, master_pdf, formset)
                    self.message_user(request, f"Erfolgreich: Stimmen für '{piece.title}' wurden erstellt.", messages.SUCCESS)
                    return redirect('admin:scorelib_piece_changelist')
                except Exception as e:
                    self.message_user(request, f"Fehler beim Splitten: {str(e)}", messages.ERROR)
        else:
            formset = PartSplitFormSet()

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
	
# Standard User-Admin entfernen und mit unserer Erweiterung neu setzen
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

# Standard registration for simple models
admin.site.register(Genre)
admin.site.register(Venue)
admin.site.register(AudioRecording)