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

import csv
import io
import os
import zipfile
from difflib import SequenceMatcher

from django.conf import settings
from django.contrib import admin, messages
from django.db import models
from django.forms import Textarea
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import path
from django.utils.html import format_html

from .models import AudioRecording, ExternalLink, LoanRecord, Part, Piece, ProgramItem
from .utils import get_orphaned_files


def find_similar_names(queryset, threshold=0.80):
    items = list(queryset.values_list("id", "name").order_by("name"))

    if len(items) < 2:
        return []

    similarity_graph = {}

    for i in range(len(items)):
        similarity_graph[i] = []

    for i, (_, name1) in enumerate(items):
        for j, (_, name2) in enumerate(items[i + 1 :], start=i + 1):
            norm_name1 = name1.lower().strip()
            norm_name2 = name2.lower().strip()

            if norm_name1 == norm_name2:
                continue

            matcher = SequenceMatcher(None, norm_name1, norm_name2)
            ratio = matcher.ratio()

            if ratio >= threshold:
                similarity_graph[i].append((j, ratio))
                similarity_graph[j].append((i, ratio))

    visited = set()
    clusters = []

    def dfs(node, cluster_indices):
        visited.add(node)
        cluster_indices.append(node)
        for neighbor, _ in similarity_graph[node]:
            if neighbor not in visited:
                dfs(neighbor, cluster_indices)

    for i in range(len(items)):
        if i not in visited and similarity_graph[i]:
            cluster_indices = []
            dfs(i, cluster_indices)

            cluster_entries = []
            cluster_similarities = []

            for idx in cluster_indices:
                cluster_entries.append(
                    {
                        "id": items[idx][0],
                        "name": items[idx][1],
                    }
                )
                for neighbor_idx, sim in similarity_graph[idx]:
                    if neighbor_idx in cluster_indices:
                        cluster_similarities.append(sim)

            if cluster_entries:
                avg_sim = (
                    sum(cluster_similarities) / len(cluster_similarities)
                    if cluster_similarities
                    else 0
                )
                min_sim = min(cluster_similarities) if cluster_similarities else 0

                clusters.append(
                    {
                        "entries": sorted(
                            cluster_entries, key=lambda x: x["name"].lower()
                        ),
                        "min_similarity": round(min_sim * 100, 1),
                        "avg_similarity": round(avg_sim * 100, 1),
                    }
                )

    return sorted(clusters, key=lambda x: x["avg_similarity"], reverse=True)


def get_generic_merge_response(admin_obj, request, queryset, title, action_name):
    if queryset.count() < 2:
        admin_obj.message_user(
            request, "Bitte wählen Sie mindestens zwei Einträge aus.", messages.WARNING
        )
        return None

    return render(
        request,
        "admin/generic_merge_confirmation.html",
        {
            "title": title,
            "queryset": queryset,
            "master_field_name": "master_id",
            "action_name": action_name,
        },
    )


@admin.action(description="Ausgewählte Stücke als ZIP herunterladen")
def download_parts_as_zip(modeladmin, request, queryset):
    max_size_mb = 250
    max_size_bytes = max_size_mb * 1024 * 1024

    total_size = 0
    for piece in queryset:
        for part in piece.parts.all():
            if part.pdf_file:
                try:
                    total_size += part.pdf_file.size
                except (FileNotFoundError, AttributeError):
                    continue

    if total_size > max_size_bytes:
        size_actual = total_size / (1024 * 1024)
        modeladmin.message_user(
            request,
            f"Download abgebrochen: Die Dateien sind insgesamt {size_actual:.1f} MB groß (Limit: {max_size_mb} MB). "
            "Bitte wählen Sie weniger Stücke aus.",
            level=messages.ERROR,
        )
        return HttpResponseRedirect(request.get_full_path())

    buffer = io.BytesIO()
    try:
        with zipfile.ZipFile(buffer, "w") as zip_file:
            for piece in queryset:
                for part in piece.parts.all():
                    if part.pdf_file:
                        file_path = part.pdf_file.path
                        safe_title = "".join(
                            x for x in piece.title if x.isalnum() or x in "._- "
                        )
                        safe_part = "".join(
                            x for x in part.part_name if x.isalnum() or x in "._- "
                        )
                        filename = f"{safe_title}_{safe_part}.pdf"
                        arcname = f"{safe_title}/{filename}".replace(" ", "_")
                        try:
                            zip_file.write(file_path, arcname)
                        except FileNotFoundError:
                            continue
    except Exception as e:
        modeladmin.message_user(
            request, f"Fehler beim Erstellen der ZIP: {e}", level="ERROR"
        )
        return HttpResponseRedirect(request.get_full_path())

    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type="application/zip")
    response["Content-Disposition"] = 'attachment; filename="noten_export.zip"'
    return response


@admin.action(description="Ausgewählte Stücke als CSV exportieren")
def export_pieces_csv(modeladmin, request, queryset):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="notenbank_export.csv"'

    writer = csv.writer(response, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(
        [
            "Label",
            "Title",
            "Composer",
            "Arranger",
            "Publisher",
            "Difficulty",
            "Duration",
            "Genres",
            "Concerts",
        ]
    )

    queryset = queryset.prefetch_related("genres", "concerts")

    for piece in queryset:
        genres_list = ", ".join([g.name for g in piece.genres.all()])
        concerts_list = ", ".join([c.title for c in piece.concerts.all()])

        writer.writerow(
            [
                piece.archive_label,
                piece.title,
                piece.composer.name if piece.composer else "",
                piece.arranger.name if piece.arranger else "",
                piece.publisher.name if piece.publisher else "",
                piece.difficulty,
                piece.duration,
                genres_list,
                concerts_list,
            ]
        )

    return response


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


class PartInline(admin.TabularInline):
    model = Part
    extra = 0
    fields = ("part_name", "pdf_file", "view_pdf_link")
    readonly_fields = ("view_pdf_link",)

    def view_pdf_link(self, obj):
        if obj.pdf_file:
            return format_html(
                '<a href="{}" target="_blank">📄 Öffnen</a>', obj.pdf_file.url
            )
        return "-"

    view_pdf_link.short_description = "Vorschau"


class ProgramItemInline(admin.TabularInline):
    model = ProgramItem
    extra = 3
    autocomplete_fields = ["piece"]


class ExternalLinkInline(admin.TabularInline):
    model = ExternalLink
    extra = 1


class MediaCleanupMixin:
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "cleanup-orphans/",
                self.admin_site.admin_view(self.cleanup_view),
                name="cleanup_orphans",
            ),
            path(
                "delete-orphan/",
                self.admin_site.admin_view(self.delete_orphan),
                name="delete_single_orphan",
            ),
        ]
        return custom_urls + urls

    def cleanup_view(self, request):
        orphans = get_orphaned_files()
        context = {
            **self.admin_site.each_context(request),
            "title": "Verwaiste Mediendateien bereinigen",
            "orphans": orphans,
        }
        return render(request, "admin/cleanup_orphans.html", context)

    def delete_orphan(self, request):
        if request.method == "POST":
            file_path = request.POST.get("file_path")
            full_path = os.path.join(settings.MEDIA_ROOT, file_path)
            if os.path.exists(full_path):
                os.remove(full_path)
                messages.success(request, f"Datei gelöscht: {file_path}")
        return redirect("admin:cleanup_orphans")
