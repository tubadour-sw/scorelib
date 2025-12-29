import os
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.db.models import Q
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404
from django.http import FileResponse
from .models import AudioRecording
from .models import Part

# Importiere deine Modelle
from .models import Piece, Part, Concert, MusicianProfile

@login_required
def scorelib_index(request):
    # Wir laden die recordings direkt mit, um Datenbankanfragen in der Schleife zu vermeiden
    pieces = Piece.objects.all().order_by('title').prefetch_related(
        'composer', 
        'arranger', 
        'parts', 
        'audiorecording_set' # Falls du keinen related_name='recordings' hast
    )
    return render(request, 'scorelib/index.html', {'pieces': pieces})

def scorelib_search(request):
    """Gibt Suchergebnisse als JSON zurueck."""
    query = request.GET.get('q', '')
    # Suche in Titel, Komponist oder Archiv-Nummer
    pieces = Piece.objects.filter(
        Q(title__icontains=query) | 
        Q(composer__name__icontains=query) |
        Q(archive_label__icontains=query)
    ).distinct()[:20] # Limitiert auf 20 Ergebnisse fuer Speed

    results = []
    for piece in pieces:
        # Wir holen alle Stimmen (Parts) fuer dieses Stueck
        parts = []
        for part in piece.parts.all():
            parts.append({
                'id': part.id,
                'name': part.part_name,
                'url': part.pdf_file.url
            })
        
        results.append({
            'id': piece.id,
            'title': piece.title,
            'composer': piece.composer.name if piece.composer else '',
            'label': piece.archive_label,
            'parts': parts
        })
    
    return JsonResponse({'results': results})
	
@login_required
def concert_detail_view(request, concert_id=None):
    if concert_id:
        # Ein ganz bestimmtes Konzert laden
        next_concert = get_object_or_404(Concert, pk=concert_id)
    else:
        next_concert = Concert.objects.filter(date__gte=timezone.now()).order_by('date').prefetch_related(
        'programitem_set__piece__audiorecording_set').first()
    
    context = {'concert': next_concert}

    if next_concert:
        # 2. Das Profil des eingeloggten Nutzers holen
        # (Nutzt das 'related_name=profile' aus dem Modell)
        profile = getattr(request.user, 'profile', None)
        
        program_data = []
        # Wir gehen durch das Programm des Konzerts (ueber ProgramItem fuer die Reihenfolge)
        for item in next_concert.programitem_set.all().select_related('piece'):
            piece = item.piece
            
            # 3. Filtern der Stimmen basierend auf dem Instrumenten-Filter des Nutzers
            user_parts = []
            if profile:
                all_parts = piece.parts.all()
                user_parts = [p for p in all_parts if profile.can_view_part(p.part_name)]
            
            program_data.append({
                'piece': piece,
                'user_parts': user_parts,
                'recordings': piece.audiorecording_set.filter(concert=next_concert)
            })
            
        context['program_data'] = program_data

    return render(request, 'scorelib/next_concert.html', context)

def concert_list_view(request):
    # Alle Konzerte nach Datum sortiert (neueste oben)
    concerts = Concert.objects.all().order_by('-date')
    return render(request, 'scorelib/concert_list.html', {'concerts': concerts})

@login_required
def protected_part_download(request, part_id):
    part = get_object_or_404(Part, pk=part_id)
    
    # Optional: Pruefen, ob der Musiker dieses Instrument spielen darf
    # (Nutzt die Methode aus unserem MusicianProfile Modell)
    if not request.user.is_staff: # Admins duerfen immer alles
        if not request.user.profile.can_view_part(part.part_name):
            return HttpResponse("Zugriff verweigert: Diese Stimme gehört nicht zu deinem Instrumenten-Filter.", status=403)

    # Pfad zur Datei auf der Festplatte
    file_path = part.pdf_file.path
    if os.path.exists(file_path):
        with open(file_path, 'rb') as fh:
            response = HttpResponse(fh.read(), content_type="application/pdf")
            # Öffnet das PDF im Browser statt es sofort herunterzuladen
            response['Content-Disposition'] = f'inline; filename="{os.path.basename(file_path)}"'
            return response
    raise Http404
	
@login_required
def protected_audio_download(request, audio_id):
    recording = get_object_or_404(AudioRecording, pk=audio_id)
    
    # Pfad zur Datei
    file_path = recording.audio_file.path
    
    if not os.path.exists(file_path):
        raise Http404

    # FileResponse ist effizienter fuer Streaming (Audio/Video)
    response = FileResponse(open(file_path, 'rb'), content_type="audio/mpeg")
    response['Content-Disposition'] = f'inline; filename="{os.path.basename(file_path)}"'
    return response