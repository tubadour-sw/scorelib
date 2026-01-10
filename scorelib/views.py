import os
import csv, io
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.db.models import Q, Sum
from django.db import transaction
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, Http404
from django.http import FileResponse
from django.contrib.auth.models import User
from django.utils.text import slugify

# Importiere deine Modelle
from .models import Piece, Part, Concert, Arranger, Composer, Publisher, Genre, MusicianProfile, AudioRecording, InstrumentGroup
from .forms import CSVPiecesImportForm, CSVUserImportForm, UserProfileUpdateForm

@login_required
def scorelib_index(request):
    # Wir laden die recordings direkt mit, um Datenbankanfragen in der Schleife zu vermeiden
    pieces = Piece.objects.select_related(
        'composer', 
        'arranger', 
        'publisher'
    ).order_by('title').prefetch_related(
        'concerts', 
        'genres',
        'audiorecording_set'
    )
    
    
    # Filterwerte aus der URL (GET) holen
    f_search = request.GET.get('search')
    f_genre = request.GET.get('genre')
    f_diff = request.GET.get('difficulty')
    f_comp = request.GET.get('composer')
    f_arr = request.GET.get('arranger')
    f_pub = request.GET.get('publisher')
    f_con = request.GET.get('concert')

    # Filter anwenden
    if f_search:
        pieces = pieces.filter(Q(title__icontains=f_search) | Q(archive_label__icontains=f_search))
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
        # Hier filtern wir über die Setliste (ProgramItems) des gewählten Konzerts
        pieces = pieces.filter(programitem__concert_id=f_con)

    # Dubletten verhindern (wegen ManyToMany Genres)
    pieces = pieces.distinct()
    
    context = {
        'pieces': pieces,
        'genres': Genre.objects.all().order_by('name'),
        'composers': Composer.objects.all().order_by('name'),
        'arrangers': Arranger.objects.all().order_by('name'),
        'publishers': Publisher.objects.all().order_by('name'),
        'concerts': Concert.objects.all().order_by('-date'),
        'active_filters': request.GET
    }
    return render(request, 'scorelib/index.html', context)

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
        # 1. Versuch: Das zeitlich nächste Konzert finden
        next_concert = Concert.objects.filter(
            date__isnull=False, 
            date__gte=timezone.now()
        ).order_by('date').first()
        
        # 2. Fallback: Wenn kein zukünftiges Konzert existiert, nimm das letzte/aktuellste
        if not next_concert:
            next_concert = Concert.objects.filter(
                date__isnull=False
            ).order_by('-date').first()
            
    # Falls die Datenbank komplett leer ist (gar kein Konzert), 
    # sollten wir den Rest der View überspringen oder eine Meldung zeigen
    if not next_concert:
        return render(request, 'scorelib/concert_detail.html', {'concert': None})
        
    context = {'concert': next_concert}
    
    # Die Summe aller 'duration'-Felder der Stücke im Programm berechnen
    # Wir greifen über das ProgramItem auf das Piece zu
    total_duration = next_concert.programitem_set.aggregate(
        total=Sum('piece__duration')
    )['total']

    # Falls das Programm leer ist, setzen wir die Dauer auf 0
    if not total_duration:
        from datetime import timedelta
        total_duration = timedelta(0)
        
    context['total_duration'] = total_duration
    
    # In der views.py innerhalb von concert_detail_view
    total_seconds = int(total_duration.total_seconds())
    minutes = total_seconds // 60
    seconds = total_seconds % 60

    if minutes > 60:
        hours = minutes // 60
        remaining_minutes = minutes % 60
        formatted_duration = f"{hours} Std. {remaining_minutes} Min."
    else:
        formatted_duration = f"{minutes}:{seconds:02d} Min."

    context['formatted_duration'] = formatted_duration

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

    return render(request, 'scorelib/concert_detail.html', context)

def concert_list_view(request):
    # Alle Konzerte nach Datum sortiert (neueste oben)
    concerts = Concert.objects.all().order_by('title')
    return render(request, 'scorelib/concert_list.html', {'concerts': concerts})

@login_required
def protected_part_download(request, part_id):
    part = get_object_or_404(Part, pk=part_id)
    
    # Optional: Pruefen, ob der Musiker dieses Instrument spielen darf
    # (Nutzt die Methode aus unserem MusicianProfile Modell)
    if not request.user.is_staff: # Admins duerfen immer alles
        profile = getattr(request.user, 'profile', None)
        if not profile or not profile.can_view_part(part.part_name):
            return HttpResponse("Zugriff verweigert: Diese Stimme gehört nicht zu deinem Instrumenten-Filter.", status=403)

    # Pfad zur Datei auf der Festplatte
    file_path = part.pdf_file.path
    if os.path.exists(file_path):
        with open(file_path, 'rb') as fh:
            #response = HttpResponse(fh.read(), content_type="application/pdf")
            response = FileResponse(open(file_path, 'rb'), content_type="application/pdf") 
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


def piece_csv_import(request):
    if request.method == "POST":
        form = CSVPiecesImportForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['csv_file']
            
            try:
                # utf-8-sig hilft gegen Excel-BOM Probleme
                data_set = csv_file.read().decode('utf-8-sig')
                io_string = io.StringIO(data_set)
                
                # Wir lesen die erste Zeile separat für den Check
                reader = csv.DictReader(io_string, delimiter=';')
                
                # Konsistenz-Check: Sind die Pflichtspalten vorhanden?
                # reader.fieldnames enthält die Namen der Kopfzeile
                required_columns = ['Title', 'Composer', 'Arranger']
                missing_columns = [col for col in required_columns if col not in reader.fieldnames]
                
                if missing_columns:
                    messages.error(
                        request, 
                        f"Import abgebrochen: Die CSV-Datei hat ein falsches Format. "
                        f"Es fehlen folgende Spalten: {', '.join(missing_columns)}. "
                        f"Bitte prüfen Sie die Groß-/Kleinschreibung."
                    )
                    return redirect(request.path)
                
                created_count = 0
                updated_count = 0
                with transaction.atomic():
                    for row in reader:
                        if not row.get("Title"):
                            continue
                        
                        # 1. Komponist holen oder neu anlegen
                        composer, _ = Composer.objects.get_or_create(name=row.get('Composer', '').strip())
                        
                        # 2. Arrangeur optional holen oder neu anlegen
                        arranger = None
                        if row.get('Arranger'):
                            arranger, _ = Arranger.objects.get_or_create(name=row['Arranger'].strip())
                            
                        publisher = None
                        if row.get('Publisher'):
                            publisher, _ = Publisher.objects.get_or_create(name=row['Publisher'].strip())
                        
                        # Schwierigkeitsgrad 
                        diff_raw = row.get('Difficulty', '').strip()
                        difficulty = int(diff_raw) if diff_raw.isdigit() else None
                        
                        # Dauer-Logik für DurationField
                        duration_raw = row.get('Duration', '').strip() # Angenommen die Spalte heißt jetzt so
                        duration_delta = None
                        
                        if duration_raw and ':' in duration_raw:
                            try:
                                parts = duration_raw.split(':')
                                if len(parts) == 2: # mm:ss
                                    minutes, seconds = map(int, parts)
                                    duration_delta = timedelta(minutes=minutes, seconds=seconds)
                                elif len(parts) == 3: # hh:mm:ss
                                    hours, minutes, seconds = map(int, parts)
                                    duration_delta = timedelta(hours=hours, minutes=minutes, seconds=seconds)
                            except ValueError:
                                pass # Falls Text in der Zeitspalte steht, ignorieren wir es
                                
                        # 3. Stück anlegen (nur wenn Titel + Komponist Kombi noch nicht existiert)
                        piece, created = Piece.objects.update_or_create(
                            title=row['Title'].strip(),
                            archive_label=row.get('Label', '').strip(),
                            composer=composer,
                            defaults={
                                'arranger': arranger,
                                'duration': duration_delta,
                                'difficulty': difficulty,
                                'publisher': publisher,
                            }
                        )
                        
                        # 4. Genres verknüpfen (Mehrfachnennung mit Komma möglich)
                        if row.get('Genres'):
                            genre_names = [g.strip() for g in row['Genres'].split(',')]
                            for g_name in genre_names:
                                genre, _ = Genre.objects.get_or_create(name=g_name)
                                piece.genres.add(genre)
                        
                        if row.get('Concerts'):
                            concert_names = [g.strip() for g in row['Concerts'].split(',')]
                            for c_name in concert_names:
                                concert, _ = Concert.objects.get_or_create(title=c_name)
                                piece.concerts.add(concert)
                        
                        if created:
                            created_count += 1
                        else:
                            updated_count += 1
                    
                    messages.success(request, f"Import abgeschlossen: {created_count} Stücke neu angelegt, {updated_count} Stücke aktualisiert.")
                    return redirect('admin:scorelib_piece_changelist')
            except UnicodeDecodeError:
                messages.error(request, "Fehler: Die Datei konnte nicht gelesen werden. Bitte stellen Sie sicher, dass sie als CSV (UTF-8) gespeichert wurde.")
            except Exception as e:
                messages.error(request, f"Ein unerwarteter Fehler ist aufgetreten: {e}")
    else:
        form = CSVPiecesImportForm()
    
    return render(request, 'admin/csv_pieces_import.html', {'form': form})
   

def index(request):
    # Basis-Queryset
    pieces = Piece.objects.all().select_related('composer', 'arranger', 'publisher').order_by('title')

    # Filterwerte aus der URL (GET) holen
    f_search = request.GET.get('search')
    f_genre = request.GET.get('genre')
    f_diff = request.GET.get('difficulty')
    f_comp = request.GET.get('composer')
    f_arr = request.GET.get('arranger')
    f_pub = request.GET.get('publisher')
    f_con = request.GET.get('concert')

    # Filter anwenden
    if f_search:
        pieces = pieces.filter(Q(title__icontains=f_search) | Q(archive_label__icontains=f_search))
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
        # Hier filtern wir über die Setliste (ProgramItems) des gewählten Konzerts
        pieces = pieces.filter(programitem__concert_id=f_con)

    # Dubletten verhindern (wegen ManyToMany Genres)
    pieces = pieces.distinct()

    # Daten für die Dropdowns im Template
    context = {
        'pieces': pieces,
        'genres': Genre.objects.all().order_by('name'),
        'composers': Composer.objects.all().order_by('name'),
        'arrangers': Arranger.objects.all().order_by('name'),
        'publishers': Publisher.objects.all().order_by('name'),
        'concerts': Concert.objects.all().order_by('-date'),
        # Aktive Filter zurückgeben, um "selected" im Template zu setzen
        'active_filters': request.GET
    }
    return render(request, 'scorelib/index.html', context)


from django.shortcuts import render, get_object_or_404
from .models import Piece

def piece_detail(request, pk):
    piece = get_object_or_404(Piece, pk=pk)
    user_profile = getattr(request.user, 'profile', None)
    
    # Alle Stimmen holen und alphabetisch nach Namen sortieren
    all_parts = list(piece.parts.all())
    all_parts.sort(key=lambda x: x.part_name.lower())
    
    user_parts = []

    if request.user.is_staff:
        user_parts = all_parts
    elif user_profile and user_profile.instrument_groups.exists():
        for part in all_parts:
            if user_profile.can_view_part(part.part_name):
                user_parts.append(part)
        
        # Auch die gefilterte Liste sicherheitshalber sortieren
        user_parts.sort(key=lambda x: x.part_name.lower())

    return render(request, 'scorelib/piece_detail.html', {
        'piece': piece,
        'user_parts': user_parts,
        'all_parts': all_parts,
        'recordings': piece.audiorecording_set.all(),
        'program_items': piece.programitem_set.select_related('concert').order_by('-concert__date'),
    })
    
def legal_view(request):
    return render(request, 'scorelib/legal.html')
    
import csv
from django.db import transaction
from django.utils.text import slugify
from django.contrib.auth.models import User
from django.contrib import messages
from django.shortcuts import render, redirect
from .models import InstrumentGroup, MusicianProfile
from .forms import CSVUserImportForm

@login_required
@transaction.atomic
def import_musicians(request):
    if not request.user.is_staff:
        return redirect('scorelib_index')

    available_groups = InstrumentGroup.objects.all().order_by('name')
    # Erstelle ein Set für schnellen Abgleich der Gruppennamen
    group_names_set = {g.name.lower(): g for g in available_groups}
        
    if request.method == "POST":
        form = CSVUserImportForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['csv_file']
            is_dry_run = form.cleaned_data.get('dry_run')
            
            try:
                decoded_file = csv_file.read().decode('utf-8-sig').splitlines()
                reader = csv.reader(decoded_file, delimiter=';')
            except Exception as e:
                messages.error(request, f"Datei konnte nicht gelesen werden: {e}")
                return redirect('import_musicians')

            import_results = []
            
            # Start einer globalen Transaktion
            sid = transaction.savepoint()
            
            try:
                # Header überspringen
                header = next(reader, None) 
                
                for line_num, row in enumerate(reader, start=2):
                    # Grundlegende Prüfung der Spaltenanzahl
                    if len(row) < 3:
                        import_results.append({
                            'line': line_num, 'name': "Unvollständig", 
                            'status': "Fehler: Mind. Vorname, Nachname, Instrumente nötig", 'type': 'danger'
                        })
                        continue

                    first_name = row[0].strip()
                    last_name = row[1].strip()
                    groups_raw = row[2].strip()
                    groups_final = ""
                    email = row[3].strip() if len(row) > 3 else ""
                    
                    # Generiere Userdaten
                    username = slugify(f"{first_name} {last_name}")
                    # Passwort: Leerzeichen im Nachnamen entfernen
                    raw_password = f"SKG-{last_name.replace(' ', '')}"
                    
                    # Innerer Savepoint für diese Zeile
                    row_sid = transaction.savepoint()
                    
                    try:
                        user, created = User.objects.get_or_create(
                            username=username,
                            defaults={
                                'first_name': first_name,
                                'last_name': last_name,
                                'email': email
                            }
                        )
                        
                        if created:
                            user.set_password(raw_password)
                            user.save()
                            status_text = "Neu angelegt"
                            row_type = "success"
                        else:
                            status_text = "Bereits vorhanden (aktualisiert)"
                            raw_password = "(unverändert)"
                            row_type = "warning"

                        # Profil & Instrumentengruppen
                        profile, _ = MusicianProfile.objects.get_or_create(user=user)
                        
                        # Gruppen verarbeiten
                        target_groups = [g.strip() for g in groups_raw.split(',') if g.strip()]
                        valid_groups = []
                        unknown_groups = []
                        
                        for g_name in target_groups:
                            if g_name.lower() in group_names_set:
                                valid_groups.append(group_names_set[g_name.lower()])                                
                            else:
                                unknown_groups.append(g_name)
                        
                        if valid_groups:
                            profile.instrument_groups.set(valid_groups)
                            groups_final = ", ".join(g.name for g in valid_groups)
                        
                        if unknown_groups:
                            status_text += f" | Unbekannte Gruppen: {', '.join(unknown_groups)}"
                            row_type = "warning"

                        transaction.savepoint_commit(row_sid)
                        
                        
                    except Exception as e:
                        transaction.savepoint_rollback(row_sid)
                        status_text = f"Kritischer Fehler: {str(e)}"
                        row_type = "danger"
                        raw_password = "-"

                    import_results.append({
                        'line': line_num,
                        'name': f"{first_name} {last_name}",
                        'email': email,
                        'username': username,
                        'password': raw_password,
                        'instrument_groups': groups_final,
                        'status': status_text,
                        'type': row_type
                    })

                # Abschluss der Transaktion
                if is_dry_run:
                    transaction.savepoint_rollback(sid)
                else:
                    transaction.savepoint_commit(sid)

                return render(request, "admin/csv_user_import_results.html", {
                    "results": import_results,
                    "is_dry_run": is_dry_run,
                    "title": "Import Ergebnis"
                })

            except Exception as e:
                transaction.savepoint_rollback(sid)
                messages.error(request, f"Allgemeiner Fehler beim Import: {e}")
                return redirect('import_musicians')
    else:
        form = CSVUserImportForm()
    
    return render(request, "admin/csv_user_import.html", {
        "form": form, 
        "title": "Musiker-Import",
        "available_groups": available_groups
    })


@login_required
def export_import_results_csv(request):
    if not request.user.is_staff:
        return redirect('scorelib_index')

    # Wir holen die Daten aus dem POST-Request (versteckte Felder im Formular)
    # oder alternativ: wir generieren sie aus den soeben verarbeiteten Daten.
    # Da wir sie direkt nach dem Import brauchen, ist ein Download-Button 
    # auf der Ergebnisseite am sinnvollsten.
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="musiker_zugangsdaten.csv"'
    
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['name', 'email', 'username', 'initial-password', 'instrument_groups', 'status'])

    # Die Daten werden per POST vom Ergebnis-Template gesendet
    names = request.POST.getlist('name[]')
    emails = request.POST.getlist('email[]')
    usernames = request.POST.getlist('username[]')
    passwords = request.POST.getlist('password[]')
    instrument_groups = request.POST.getlist('instrument_groups[]')
    statuses = request.POST.getlist('status[]')

    for n, e, u, p, i, s in zip(names, emails, usernames, passwords, instrument_groups, statuses):
        writer.writerow([n, e, u, p, i, s])

    return response

@login_required
def profile_view(request):
    user_profile = getattr(request.user, 'profile', None)
    
    if request.method == 'POST':
        form = UserProfileUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profil erfolgreich aktualisiert!")
            return redirect('profile_view')
    else:
        form = UserProfileUpdateForm(instance=request.user)
    
    context = {
        'form': form,
        'user_profile': user_profile,
    }
    return render(request, 'registration/profile.html', context)