import shutil

from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import format_html

from ..admin_actions import MediaCleanupMixin
from ..models import SiteSettings, Venue


@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    search_fields = ["name"]
    list_display = ("name", "address")


@admin.register(SiteSettings)
class SiteSettingsAdmin(MediaCleanupMixin, admin.ModelAdmin):
    list_display = ("site_title", "audio_ripping_enabled")
    readonly_fields = ("ffmpeg_status_display", "cleanup_link")

    fieldsets = (
        (None, {"fields": ("site_title", "band_name", "legal_text")}),
        (
            "Audio-Ripping",
            {"fields": ("audio_ripping_enabled", "ffmpeg_status_display")},
        ),
        ("Wartung", {"fields": ("cleanup_link",)}),
    )

    def has_add_permission(self, request):
        return SiteSettings.objects.count() == 0

    def changelist_view(self, request, extra_context=None):
        obj = SiteSettings.get_solo()
        url = reverse("admin:scorelib_sitesettings_change", args=[obj.pk])
        return redirect(url)

    def ffmpeg_status_display(self, obj):
        ffmpeg_path = shutil.which("ffmpeg")
        if ffmpeg_path:
            return format_html(
                '<span style="color: green;">✔ ffmpeg gefunden: {}</span>', ffmpeg_path
            )
        return format_html(
            '<span style="color: red;">✘ ffmpeg nicht im Systempfad gefunden.</span>'
        )

    ffmpeg_status_display.short_description = "System-Check"

    def save_model(self, request, obj, form, change):
        if obj.audio_ripping_enabled and not shutil.which("ffmpeg"):
            obj.audio_ripping_enabled = False
            messages.error(
                request,
                "Feature konnte nicht aktiviert werden: ffmpeg wurde auf diesem Server nicht gefunden.",
            )
        super().save_model(request, obj, form, change)

    def cleanup_link(self, obj):
        url = reverse("admin:cleanup_orphans")
        return format_html(
            '<a href="{}" class="button" style="background: #79aec8;">🧹 Jetzt Medien-Bereinigung öffnen</a>',
            url,
        )

    cleanup_link.short_description = "Datenbank-Hygiene"
