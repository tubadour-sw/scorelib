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

import os

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from ...models import AudioRecording, Concert, Piece, ProgramItem


@require_POST
@login_required
def process_single_audio(request):
    if not request.user.is_staff:
        return JsonResponse(
            {"status": "error", "message": "Zugriff verweigert."}, status=403
        )

    try:
        piece_id = request.POST.get("piece_id")
        concert_id = request.POST.get("concert_id")
        description = request.POST.get("description", "")
        audio_file = request.FILES.get("audio_file")

        if not audio_file:
            return JsonResponse(
                {"status": "error", "message": "Keine Audio-Datei hochgeladen."},
                status=400,
            )

        piece = get_object_or_404(Piece, pk=piece_id)
        concert = get_object_or_404(Concert, pk=concert_id)

        temp_filename = f"rip_T{piece_id}_{audio_file.name}"
        temp_dir = os.path.join(settings.MEDIA_ROOT, "temp")
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, temp_filename)

        with open(temp_path, "wb+") as f:
            for chunk in audio_file.chunks():
                f.write(chunk)

        AudioRecording.objects.create(
            piece=piece,
            concert=concert,
            description=description,
            audio_file=os.path.join("temp", temp_filename),
        )

        return JsonResponse({"status": "success", "piece": piece.title})

    except Exception as e:
        import traceback

        print(traceback.format_exc())
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@login_required
def audio_ripping_page(request, concert_id):
    if not request.user.is_staff:
        return redirect("scorelib_index")

    concert = get_object_or_404(Concert, pk=concert_id)
    program_items = ProgramItem.objects.filter(concert=concert).order_by("order")

    for item in program_items:
        item.existing_recordings = AudioRecording.objects.filter(
            concert=concert, piece=item.piece
        )

    context = {
        "concert": concert,
        "program_items": program_items,
        "title": f"CD-Tracks zuordnen: {concert.title}",
    }
    return render(request, "admin/audio_ripping.html", context)


@require_POST
@login_required
def delete_audio_recording(request):
    if not request.user.is_staff:
        return JsonResponse(
            {"status": "error", "message": "Zugriff verweigert."}, status=403
        )

    recording_id = request.POST.get("recording_id")
    recording = get_object_or_404(AudioRecording, pk=recording_id)

    try:
        if recording.audio_file and os.path.exists(recording.audio_file.path):
            os.remove(recording.audio_file.path)

        recording.delete()
        return JsonResponse({"status": "success"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)
