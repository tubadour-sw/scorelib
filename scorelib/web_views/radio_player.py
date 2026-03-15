from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from ..models import AudioRecording

@login_required
def radio_player_view(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'remove':
            id_to_remove = request.POST.get('id')
            session_ids = request.session.get('playlist_ids', [])
            if id_to_remove in session_ids:
                session_ids.remove(id_to_remove)
                request.session['playlist_ids'] = session_ids
        elif action == 'clear':
            request.session['playlist_ids'] = []
        elif action == 'move_up':
            track_id = request.POST.get('id')
            session_ids = request.session.get('playlist_ids', [])
            if track_id in session_ids:
                idx = session_ids.index(track_id)
                if idx > 0:
                    session_ids[idx], session_ids[idx-1] = session_ids[idx-1], session_ids[idx]
                    request.session['playlist_ids'] = session_ids
        elif action == 'move_down':
            track_id = request.POST.get('id')
            session_ids = request.session.get('playlist_ids', [])
            if track_id in session_ids:
                idx = session_ids.index(track_id)
                if idx < len(session_ids) - 1:
                    session_ids[idx], session_ids[idx+1] = session_ids[idx+1], session_ids[idx]
                    request.session['playlist_ids'] = session_ids
        return HttpResponse('ok')
    
    # 1. Schauen, ob neue Tracks über die URL reinkommen (vom Konzert-Button)
    new_track_ids = request.GET.getlist('tracks')
    
    if new_track_ids:
        # Wenn neue IDs kommen, überschreiben wir die aktuelle Playlist in der Session
        current_ids = request.session.get('playlist_ids', [])
        for tid in new_track_ids:
            if tid not in current_ids:
                current_ids.append(tid)
        request.session['playlist_ids'] = current_ids
            
    # 2. IDs aus der Session holen (falls vorhanden)
    session_ids = request.session.get('playlist_ids', [])
    
    # 3. Datenbank-Abfrage
    tracks = AudioRecording.objects.filter(id__in=session_ids)
    
    # Sortierung wie in der Session beibehalten
    id_map = {str(t.id): t for t in tracks}
    sorted_tracks = [id_map[tid] for tid in session_ids if tid in id_map]

    return render(request, 'scorelib/radio_player.html', {'tracks': sorted_tracks})