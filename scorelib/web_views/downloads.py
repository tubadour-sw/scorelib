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

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404

from ..models import AudioRecording, Part


@login_required
def protected_part_download(request, part_id):
    part = get_object_or_404(Part, pk=part_id)

    if not request.user.is_staff:
        profile = getattr(request.user, "profile", None)
        piece = part.piece
        if not profile:
            return HttpResponse(
                "Zugriff verweigert: Du hast keinen Zugriff auf Noten.", status=403
            )

        if not profile.has_full_archive_access:
            if not piece.is_active_for_download():
                return HttpResponse(
                    "Zugriff verweigert: Noten für dieses Stück stehen momentan nicht zur Verfügung.",
                    status=403,
                )

            if not profile.can_view_part(part.part_name):
                return HttpResponse(
                    "Zugriff verweigert: Diese Stimme gehört nicht zu deinem Instrumenten-Filter.",
                    status=403,
                )

    file_path = part.pdf_file.path
    if os.path.exists(file_path):
        response = FileResponse(open(file_path, "rb"), content_type="application/pdf")
        response["Content-Disposition"] = (
            f'inline; filename="{os.path.basename(file_path)}"'
        )
        return response
    raise Http404


@login_required
def protected_audio_download(request, audio_id):
    recording = get_object_or_404(AudioRecording, pk=audio_id)
    file_path = recording.audio_file.path

    if not os.path.exists(file_path):
        raise Http404

    response = FileResponse(open(file_path, "rb"), content_type="audio/mpeg")
    response["Content-Disposition"] = (
        f'inline; filename="{os.path.basename(file_path)}"'
    )
    return response
