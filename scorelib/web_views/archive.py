import os

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from ..models import Arranger, Composer, Concert, Genre, Piece, Publisher


@login_required
def scorelib_index(request):
    pieces = (
        Piece.objects.select_related("composer", "arranger", "publisher")
        .order_by("title")
        .prefetch_related("concerts", "genres", "audiorecording_set")
    )

    f_search = request.GET.get("search")
    f_genre = request.GET.get("genre")
    f_diff = request.GET.get("difficulty")
    f_comp = request.GET.get("composer")
    f_arr = request.GET.get("arranger")
    f_pub = request.GET.get("publisher")
    f_con = request.GET.get("concert")
    f_sort = request.GET.get("sort", "title")
    f_sort_dir = request.GET.get("sort_dir", "asc")
    f_sort_artist = request.GET.get("sort_artist", "composer")

    if f_search:
        pieces = pieces.filter(
            Q(title__icontains=f_search)
            | Q(archive_label__icontains=f_search)
            | Q(composer__name__icontains=f_search)
            | Q(arranger__name__icontains=f_search)
            | Q(additional_info__icontains=f_search)
        )
    if f_genre:
        pieces = pieces.filter(genres__id=f_genre)
    if f_diff:
        pieces = pieces.filter(difficulty=f_diff)
    if f_comp:
        pieces = pieces.filter(composer__id=f_comp)
    if f_arr:
        pieces = pieces.filter(arranger__id=f_arr)
    if f_pub:
        pieces = pieces.filter(publisher__id=f_pub)
    if f_con:
        pieces = pieces.filter(programitem__concert_id=f_con)

    pieces = pieces.distinct()

    f_sort_artist = request.GET.get("sort_artist", "composer")

    if f_sort == "title":
        order_field = "title"
    elif f_sort == "composer":
        order_field = (
            "arranger__name" if f_sort_artist == "arranger" else "composer__name"
        )
    elif f_sort == "publisher":
        order_field = "publisher__name"
    elif f_sort == "difficulty":
        order_field = "difficulty"
    elif f_sort == "label":
        order_field = "archive_label"
    else:
        order_field = "title"

    if f_sort_dir == "desc":
        order_field = f"-{order_field}"

    pieces = pieces.order_by(order_field)

    paginator = Paginator(pieces, 50)
    page_number = request.GET.get("page", 1)
    try:
        page_obj = paginator.page(page_number)
    except Exception:
        page_obj = paginator.page(1)

    context = {
        "pieces": page_obj.object_list,
        "page_obj": page_obj,
        "genres": Genre.objects.all().order_by("name"),
        "composers": Composer.objects.all().order_by("name"),
        "arrangers": Arranger.objects.all().order_by("name"),
        "publishers": Publisher.objects.all().order_by("name"),
        "concerts": Concert.objects.all().order_by("-date"),
        "active_filters": request.GET,
        "current_sort": f_sort,
        "current_sort_dir": f_sort_dir,
        "current_sort_artist": f_sort_artist,
        "total_count": paginator.count,
    }
    return render(request, "scorelib/index.html", context)


@login_required
def scorelib_search(request):
    query = request.GET.get("q", "")
    user_profile = getattr(request.user, "profile", None)
    has_full_archive_access = request.user.is_staff or (
        user_profile and user_profile.has_full_archive_access
    )

    pieces = (
        Piece.objects.filter(
            Q(title__icontains=query)
            | Q(additional_info__icontains=query)
            | Q(composer__name__icontains=query)
            | Q(arranger__name__icontains=query)
            | Q(archive_label__icontains=query)
        )
        .distinct()
        .prefetch_related("parts")[:20]
    )

    results = []
    for piece in pieces:
        if has_full_archive_access:
            allowed_parts = piece.parts.all()
        elif user_profile and piece.is_active_for_download():
            allowed_parts = [
                p for p in piece.parts.all() if user_profile.can_view_part(p.part_name)
            ]
        else:
            allowed_parts = []

        parts = [
            {
                "id": part.id,
                "name": part.part_name,
                "url": reverse("protected_part_download", args=[part.id]),
            }
            for part in allowed_parts
        ]

        results.append(
            {
                "id": piece.id,
                "title": piece.title,
                "composer": piece.composer.name if piece.composer else "",
                "label": piece.archive_label,
                "parts": parts,
            }
        )

    return JsonResponse({"results": results})


def index(request):
    pieces = (
        Piece.objects.all()
        .select_related("composer", "arranger", "publisher")
        .order_by("title")
    )

    f_search = request.GET.get("search")
    f_genre = request.GET.get("genre")
    f_diff = request.GET.get("difficulty")
    f_comp = request.GET.get("composer")
    f_arr = request.GET.get("arranger")
    f_pub = request.GET.get("publisher")
    f_con = request.GET.get("concert")

    if f_search:
        pieces = pieces.filter(
            Q(title__icontains=f_search) | Q(archive_label__icontains=f_search)
        )
    if f_genre:
        pieces = pieces.filter(genres__id=f_genre)
    if f_diff:
        pieces = pieces.filter(difficulty=f_diff)
    if f_comp:
        pieces = pieces.filter(composer__id=f_comp)
    if f_arr:
        pieces = pieces.filter(arranger__id=f_arr)
    if f_pub:
        pieces = pieces.filter(publisher__id=f_pub)
    if f_con:
        pieces = pieces.filter(programitem__concert_id=f_con)

    pieces = pieces.distinct()

    context = {
        "pieces": pieces,
        "genres": Genre.objects.all().order_by("name"),
        "composers": Composer.objects.all().order_by("name"),
        "arrangers": Arranger.objects.all().order_by("name"),
        "publishers": Publisher.objects.all().order_by("name"),
        "concerts": Concert.objects.all().order_by("-date"),
        "active_filters": request.GET,
    }
    return render(request, "scorelib/index.html", context)


@login_required
def piece_detail(request, pk):
    piece = get_object_or_404(Piece, pk=pk)
    user_profile = getattr(request.user, "profile", None)

    all_parts = list(piece.parts.all())
    all_parts.sort(key=lambda x: x.part_name.lower())

    user_parts = []

    if request.user.is_staff or (user_profile and user_profile.has_full_archive_access):
        user_parts = all_parts
    elif (
        user_profile
        and user_profile.instrument_groups.exists()
        and piece.is_active_for_download()
    ):
        user_parts = [
            part for part in all_parts if user_profile.can_view_part(part.part_name)
        ]
        user_parts.sort(key=lambda x: x.part_name.lower())

    return render(
        request,
        "scorelib/piece_detail.html",
        {
            "piece": piece,
            "user_parts": user_parts,
            "all_parts": all_parts,
            "recordings": piece.audiorecording_set.all(),
            "program_items": piece.programitem_set.select_related("concert").order_by(
                "-concert__date"
            ),
        },
    )
