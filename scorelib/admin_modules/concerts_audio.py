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

from django.contrib import admin
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.html import format_html

from ..admin_actions import ProgramItemInline, get_generic_merge_response
from ..models import AudioRecording, Concert, Piece, SiteSettings


@admin.register(Concert)
class ConcertAdmin(admin.ModelAdmin):
    list_display = ("title", "subtitle", "date", "venue")
    list_filter = ("date", "venue")
    search_fields = ["title", "subtitle"]
    autocomplete_fields = ("venue",)
    inlines = [ProgramItemInline]
    readonly_fields = ("rip_audio_link",)
    actions = ["merge_concerts_action"]

    fieldsets = (
        (None, {"fields": ("title", "subtitle", "date", "venue", "poster")}),
        (
            "Audio-Verarbeitung",
            {
                "fields": ("rip_audio_link",),
                "description": "Hier können Sie Audio-Aufnahmen für dieses Konzert verarbeiten.",
            },
        ),
    )

    def merge_concerts_action(self, request, queryset):
        if "apply" in request.POST:
            master_id = request.POST.get("master_id")
            master = get_object_or_404(Concert, pk=master_id)
            others = queryset.exclude(pk=master.pk)

            for other in others:
                current_max_order = master.programitem_set.count()
                for item in other.programitem_set.all():
                    current_max_order += 1
                    item.concert = master
                    item.order = current_max_order
                    item.save()
                other.delete()

            self.message_user(request, "Konzerte erfolgreich zusammengeführt.")
            return HttpResponseRedirect(request.get_full_path())

        return get_generic_merge_response(
            self, request, queryset, "Konzerte mergen", "merge_concerts_action"
        )

    merge_concerts_action.short_description = "Ausgewählte Concerts zusammenführen"

    def rip_audio_link(self, obj):
        if not obj.pk:
            return "-"

        site_settings = SiteSettings.get_solo()

        if site_settings and site_settings.audio_ripping_enabled:
            url = reverse("audio_ripping_page", args=[obj.pk])
            return format_html(
                '<a class="button" href="{}" style="background-color: #417690; color: white;">'
                "💿 CD-Tracks für dieses Konzert hochladen</a>",
                url,
            )
        return "Feature in den Site-Settings deaktiviert oder ffmpeg fehlt."

    rip_audio_link.short_description = "Audio-Verarbeitung"


@admin.register(AudioRecording)
class AudioRecordingAdmin(admin.ModelAdmin):
    list_display = ("piece", "concert", "description", "audio_file_link")
    list_filter = ("concert__title", "concert__date")

    search_fields = (
        "piece__title",
        "piece__additional_info",
        "concert__title",
        "concert__subtitle",
    )
    autocomplete_fields = ["piece", "concert"]

    def audio_file_link(self, obj):
        if obj.audio_file:
            return format_html(
                '<a href="{}" target="_blank">📄 Datei öffnen</a>', obj.audio_file.url
            )
        return "Keine Datei"

    audio_file_link.short_description = "Audio"

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)

        concert_id = None
        if "concert" in request.GET:
            concert_id = request.GET.get("concert")
            form.base_fields["concert"].initial = concert_id
        elif obj and obj.concert:
            concert_id = obj.concert.id
        elif request.method == "POST":
            concert_id = request.POST.get("concert")

        if concert_id:
            form.base_fields["piece"].queryset = Piece.objects.filter(
                programitem__concert_id=concert_id
            ).distinct()
        else:
            form.base_fields["piece"].queryset = Piece.objects.none()

        return form

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "concert":
            kwargs["queryset"] = Concert.objects.order_by("title")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    class Media:
        js = ("admin/js/jquery.init.js", "js/audio_recording_helper.js")
