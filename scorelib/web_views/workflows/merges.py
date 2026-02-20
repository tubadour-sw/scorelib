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

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse

from ...models import Arranger, Composer, Piece, Publisher


@login_required
def suggest_merges_page(request, model_name):
    from ...admin import find_similar_names

    model_map = {
        "composer": Composer,
        "arranger": Arranger,
        "publisher": Publisher,
    }

    if model_name not in model_map:
        raise Http404("Model not found")

    Model = model_map[model_name]
    all_items = Model.objects.all()
    clusters = find_similar_names(all_items, threshold=0.80)

    request.session["duplicate_clusters"] = clusters
    request.session.modified = True

    model_display = {
        "composer": "Composer",
        "arranger": "Arranger",
        "publisher": "Publisher",
    }

    context = {
        "title": f"{model_display.get(model_name, model_name)}-Vorschläge zusammenführen",
        "clusters": clusters,
        "model_name": model_name,
    }

    return render(request, "admin/suggest_merges.html", context)


@login_required
def merge_cluster_confirm(request, model_name):
    model_map = {
        "composer": Composer,
        "arranger": Arranger,
        "publisher": Publisher,
    }

    if model_name not in model_map:
        raise Http404("Model not found")

    Model = model_map[model_name]
    clusters = request.session.get("duplicate_clusters")
    cluster_index = request.POST.get("cluster_index")

    if not clusters:
        messages.error(request, "Ungültige Anfrage - Keine Cluster in Session.")
        return redirect(f"admin:scorelib_{model_name}_changelist")

    if cluster_index is None:
        messages.error(request, "Ungültige Anfrage - Keine cluster_index.")
        return redirect(f"admin:scorelib_{model_name}_changelist")

    try:
        cluster_index = int(cluster_index)
        cluster = clusters[cluster_index]
    except (ValueError, IndexError) as e:
        messages.error(request, f"Ungültige Cluster-Daten: {e}")
        return redirect(f"admin:scorelib_{model_name}_changelist")

    entry_ids = [entry["id"] for entry in cluster["entries"]]
    entries_dict = {obj.id: obj for obj in Model.objects.filter(id__in=entry_ids)}

    if len(entries_dict) != len(entry_ids):
        messages.error(request, "Einige Einträge wurden nicht gefunden.")
        return redirect(f"admin:scorelib_{model_name}_changelist")

    if "master_id" in request.POST:
        master_id = int(request.POST.get("master_id"))

        if master_id not in entries_dict:
            messages.error(request, "Ungültige Master-Auswahl.")
            return redirect(
                "merge_cluster_confirm",
                model_name=model_name,
                cluster_index=cluster_index,
            )

        master = entries_dict[master_id]
        merge_ids = [int(id) for id in request.POST.getlist("merge_ids")]
        merge_ids = [id for id in merge_ids if id != master_id]

        if not merge_ids:
            messages.warning(request, "Keine Einträge zum Zusammenführen ausgewählt.")
            return redirect(f"admin:scorelib_{model_name}_changelist")

        if model_name == "composer":
            Piece.objects.filter(composer_id__in=merge_ids).update(composer=master)
        elif model_name == "arranger":
            Piece.objects.filter(arranger_id__in=merge_ids).update(arranger=master)
        elif model_name == "publisher":
            Piece.objects.filter(publisher_id__in=merge_ids).update(publisher=master)

        Model.objects.filter(id__in=merge_ids).delete()

        count = len(merge_ids)
        messages.success(
            request,
            f"Erfolgreich {count} Eintrag(e) in '{master.name}' zusammengeführt",
        )

        return redirect(reverse("suggest_merges_page", args=[model_name]))

    cluster_entries = [entries_dict[entry["id"]] for entry in cluster["entries"]]
    back_url = reverse("suggest_merges_page", args=[model_name])

    context = {
        "title": f"{model_name.capitalize()} zusammenführen - Cluster",
        "entries": cluster_entries,
        "cluster": cluster,
        "cluster_index": cluster_index,
        "model_name": model_name,
        "back_url": back_url,
    }
    return render(request, "admin/merge_cluster_confirm.html", context)
