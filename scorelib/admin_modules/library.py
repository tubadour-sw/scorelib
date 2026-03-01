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
from django.utils.html import format_html
from django.http import HttpResponseRedirect, HttpResponse
from django.db import models
from django.forms import Textarea

from ..models import (
    Piece,
    Part,
    ExternalLink,
    Composer,
    Arranger,
    Publisher,
    Genre,
    LoanRecord,
    InstrumentGroup,
)
from ..forms import PartSplitFormSet
from ..utils import process_pdf_split
from ..views import piece_csv_import

from ..admin_actions import (
    PartInline,
    ExternalLinkInline,
    download_parts_as_zip,
    export_pieces_csv,
    get_generic_merge_response,
    MediaCleanupMixin,
)


class LoanRecordInline(admin.TabularInline):
    model = LoanRecord
    extra = 0
    classes = ["collapse"]
    verbose_name = "Verleih-Historie"
    fields = ("partner_name", "loan_date", "return_date", "notes")
    formfield_overrides = {
        models.TextField: {
            "widget": Textarea(
                attrs={
                    "rows": 1,
                    "cols": 30,
                    "style": "height: 2em; min-height: 2em; transition: height 0.2s;",
                }
            )
        },
    }


@admin.register(Piece)
class PieceAdmin(MediaCleanupMixin, admin.ModelAdmin):
    inlines = [ExternalLinkInline, LoanRecordInline, PartInline]
    filter_horizontal = ("genres",)
    autocomplete_fields = ("composer", "arranger", "publisher")
    readonly_fields = ("download_button",)

    fieldsets = (
        (
            "Basis-Informationen",
            {
                "fields": (
                    "title",
                    "additional_info",
                    "archive_label",
                    "is_owned_by_orchestra",
                )
            },
        ),
        (
            "Musikalische Details",
            {
                "fields": (
                    "composer",
                    "arranger",
                    "publisher",
                    "genres",
                    "is_medley",
                    "duration",
                    "difficulty",
                )
            },
        ),
        (
            "Aktionen",
            {
                "fields": ("download_button",),
            },
        ),
    )

    list_display = (
        "title",
        "archive_label",
        "composer",
        "arranger",
        "publisher",
        "display_genres",
        "get_status_display",
        "view_parts_link",
    )
    list_filter = (
        "genres",
        "composer",
        "arranger",
        "difficulty",
        "publisher",
        "is_owned_by_orchestra",
    )
    search_fields = (
        "title",
        "archive_label",
        "composer__name",
        "arranger__name",
        "additional_info",
    )
    list_editable = ("archive_label",)
    list_display_links = ("title",)
    actions = [download_parts_as_zip, export_pieces_csv]
    ordering = ("title",)

    class Media:
        js = ("admin/js/jquery.init.js", "js/admin_filter_collapse.js")
        css = {"all": ("css/admin_custom.css",)}

    def get_status_display(self, obj):
        return obj.current_status["label"]

    get_status_display.short_description = "Status"

    def display_genres(self, obj):
        return ", ".join([genre.name for genre in obj.genres.all()])

    display_genres.short_description = "Genres"

    def download_button(self, obj):
        if obj.pk:
            url = reverse("admin:piece-download-zip", args=[obj.pk])
            return format_html(
                '<a class="button" href="{}" style="background: #417690; '
                'color: white; padding: 10px 15px; border-radius: 4px; '
                'text-decoration: none;">'
                "📄 Alle Stimmen als ZIP herunterladen"
                "</a>",
                url,
            )
        return "Speichere das Stück zuerst."

    download_button.short_description = "Export PDFs als ZIP"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:piece_id>/change/split/",
                self.admin_site.admin_view(self.split_view),
                name="piece-split",
            ),
            path(
                "import-csv/",
                self.admin_site.admin_view(piece_csv_import),
                name="piece_csv_import",
            ),
            path(
                "<int:object_id>/download-zip/",
                self.admin_site.admin_view(self.download_single_piece_zip),
                name="piece-download-zip",
            ),
        ]
        return custom_urls + urls

    def download_single_piece_zip(self, request, object_id):
        return download_parts_as_zip(self, request, Piece.objects.filter(pk=object_id))

    def view_parts_link(self, obj):
        count = obj.parts.count()
        url = reverse("admin:scorelib_part_changelist") + f"?piece__id__exact={obj.pk}"
        return format_html('<a href="{}">{} Stimmen anzeigen</a>', url, count)

    view_parts_link.short_description = "Einzelstimmen"

    def split_view(self, request, piece_id):
        piece = get_object_or_404(Piece, pk=piece_id)
        existing_part_names = (
            Part.objects.order_by("part_name")
            .values_list("part_name", flat=True)
            .distinct()
        )

        if request.method == "POST":
            formset = PartSplitFormSet(request.POST)
            master_pdf = request.FILES.get("master_pdf")

            if formset.is_valid() and master_pdf:
                valid_data_list = []
                for form_data in formset.cleaned_data:
                    if form_data.get("part_name") and form_data.get("pages"):
                        valid_data_list.append(form_data)

                if not valid_data_list:
                    self.message_user(
                        request,
                        "Bitte geben Sie bei mindestens einer Stimme sowohl den Namen "
                        "als auch die Seiten an.",
                        messages.WARNING,
                    )
                else:
                    try:
                        process_pdf_split(piece, master_pdf, valid_data_list)
                        self.message_user(
                            request,
                            f"Erfolgreich: Stimmen für '{piece.title}' wurden erstellt.",
                            messages.SUCCESS,
                        )
                        return redirect("admin:scorelib_piece_change", piece.id)
                    except Exception as e:
                        self.message_user(
                            request, f"Fehler beim Splitten: {str(e)}", messages.ERROR
                        )
            else:
                self.message_user(
                    request,
                    "Das Formular ist ungültig. Bitte prüfen Sie Ihre Eingaben.",
                    messages.ERROR,
                )
        else:
            formset = PartSplitFormSet()

        context = {
            **self.admin_site.each_context(request),
            "piece": piece,
            "formset": formset,
            "existing_part_names": existing_part_names,
            "title": f"PDF Splitten: {piece.title}",
            "opts": self.model._meta,
        }
        return render(request, "admin/split_pdf_form.html", context)


@admin.register(Part)
class PartAdmin(admin.ModelAdmin):
    list_display = ("piece", "part_name", "pdf_file")
    search_fields = ("piece__title", "part_name")
    autocomplete_fields = ("piece",)


@admin.register(ExternalLink)
class ExternalLinkAdmin(admin.ModelAdmin):
    list_display = ("piece", "title", "url")
    search_fields = ("piece__title", "title")
    autocomplete_fields = ("piece",)


@admin.register(Composer)
class ComposerAdmin(admin.ModelAdmin):
    search_fields = ("name",)
    list_display = ("name",)
    actions = ["merge_composers_action", "suggest_merge_composers_action"]

    def merge_composers_action(self, request, queryset):
        if "apply" in request.POST:
            master_id = request.POST.get("master_id")
            master = get_object_or_404(Composer, pk=master_id)
            others = queryset.exclude(pk=master.pk)
            Piece.objects.filter(composer__in=others).update(composer=master)
            others.delete()
            self.message_user(
                request, f"Erfolgreich in {master.name} zusammengeführt."
            )
            return HttpResponseRedirect(request.get_full_path())

        return get_generic_merge_response(
            self, request, queryset, "Composer mergen", "merge_composers_action"
        )

    merge_composers_action.short_description = "Ausgewählte Composer zusammenführen"

    def suggest_merge_composers_action(self, request, queryset):
        return redirect(reverse("suggest_merges_page", args=["composer"]))

    suggest_merge_composers_action.short_description = "Mögliche Duplikate vorschlagen"


@admin.register(Arranger)
class ArrangerAdmin(admin.ModelAdmin):
    search_fields = ("name",)
    list_display = ("name",)
    actions = ["merge_arrangers_action", "suggest_merge_arrangers_action"]

    def merge_arrangers_action(self, request, queryset):
        if "apply" in request.POST:
            master_id = request.POST.get("master_id")
            master = get_object_or_404(Arranger, pk=master_id)
            others = queryset.exclude(pk=master.pk)
            Piece.objects.filter(arranger__in=others).update(arranger=master)
            others.delete()
            self.message_user(
                request, f"Erfolgreich in {master.name} zusammengeführt."
            )
            return HttpResponseRedirect(request.get_full_path())

        return get_generic_merge_response(
            self, request, queryset, "Arranger mergen", "merge_arrangers_action"
        )

    merge_arrangers_action.short_description = "Ausgewählte Arranger zusammenführen"

    def suggest_merge_arrangers_action(self, request, queryset):
        return redirect(reverse("suggest_merges_page", args=["arranger"]))

    suggest_merge_arrangers_action.short_description = "Mögliche Duplikate vorschlagen"


@admin.register(Publisher)
class PublisherAdmin(admin.ModelAdmin):
    search_fields = ("name",)
    list_display = ("name",)
    actions = ["merge_publisher_action", "suggest_merge_publisher_action"]

    def merge_publisher_action(self, request, queryset):
        if "apply" in request.POST:
            master_id = request.POST.get("master_id")
            master = get_object_or_404(Publisher, pk=master_id)
            others = queryset.exclude(pk=master.pk)
            Piece.objects.filter(publisher__in=others).update(publisher=master)
            others.delete()
            self.message_user(
                request, f"Erfolgreich in {master.name} zusammengeführt."
            )
            return HttpResponseRedirect(request.get_full_path())

        return get_generic_merge_response(
            self, request, queryset, "Publisher mergen", "merge_publisher_action"
        )

    merge_publisher_action.short_description = "Ausgewählte Publisher zusammenführen"

    def suggest_merge_publisher_action(self, request, queryset):
        return redirect(reverse("suggest_merges_page", args=["publisher"]))

    suggest_merge_publisher_action.short_description = "Mögliche Duplikate vorschlagen"


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(InstrumentGroup)
class InstrumentGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "filter_strings")

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "unmatched-parts/",
                self.admin_site.admin_view(self.unmatched_parts_view),
                name="unmatched-parts",
            ),
        ]
        return custom_urls + urls

    def unmatched_parts_view(self, request):
        all_parts = Part.objects.select_related("piece").all()
        all_groups = InstrumentGroup.objects.all()

        unmatched = []
        for part in all_parts:
            if not any(group.matches_part(part.part_name) for group in all_groups):
                unmatched.append(part)

        context = {
            **self.admin_site.each_context(request),
            "title": "Verwaiste Stimmen (Keine Gruppe passt)",
            "unmatched_parts": unmatched,
            "opts": self.model._meta,
        }
        return render(request, "admin/unmatched_parts.html", context)
