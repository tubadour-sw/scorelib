import csv
import io

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils.text import slugify

from ...forms import CSVPiecesImportForm, CSVUserImportForm
from ...models import (
    Arranger,
    Composer,
    Concert,
    Genre,
    InstrumentGroup,
    MusicianProfile,
    Piece,
    Publisher,
)


def piece_csv_import(request):
    if request.method == "POST":
        form = CSVPiecesImportForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES["csv_file"]

            try:
                data_set = csv_file.read().decode("utf-8-sig")
                io_string = io.StringIO(data_set)
                reader = csv.DictReader(io_string, delimiter=";")

                required_columns = ["Title", "Composer", "Arranger"]
                missing_columns = [
                    col for col in required_columns if col not in reader.fieldnames
                ]

                if missing_columns:
                    messages.error(
                        request,
                        f"Import abgebrochen: Die CSV-Datei hat ein falsches Format. "
                        f"Es fehlen folgende Spalten: {', '.join(missing_columns)}. "
                        f"Bitte prüfen Sie die Groß-/Kleinschreibung.",
                    )
                    return redirect(request.path)

                created_count = 0
                updated_count = 0
                with transaction.atomic():
                    for row in reader:
                        if not row.get("Title"):
                            continue

                        composer, _ = Composer.objects.get_or_create(
                            name=row.get("Composer", "").strip()
                        )

                        arranger = None
                        if row.get("Arranger"):
                            arranger, _ = Arranger.objects.get_or_create(
                                name=row["Arranger"].strip()
                            )

                        publisher = None
                        if row.get("Publisher"):
                            publisher, _ = Publisher.objects.get_or_create(
                                name=row["Publisher"].strip()
                            )

                        diff_raw = row.get("Difficulty", "").strip()
                        difficulty = int(diff_raw) if diff_raw.isdigit() else None

                        duration_raw = row.get("Duration", "").strip()
                        duration_delta = None

                        if duration_raw and ":" in duration_raw:
                            try:
                                parts = duration_raw.split(":")
                                if len(parts) == 2:
                                    minutes, seconds = map(int, parts)
                                    duration_delta = timedelta(
                                        minutes=minutes, seconds=seconds
                                    )
                                elif len(parts) == 3:
                                    hours, minutes, seconds = map(int, parts)
                                    duration_delta = timedelta(
                                        hours=hours, minutes=minutes, seconds=seconds
                                    )
                            except ValueError:
                                pass

                        piece, created = Piece.objects.update_or_create(
                            title=row["Title"].strip(),
                            archive_label=row.get("Label", "").strip(),
                            composer=composer,
                            defaults={
                                "arranger": arranger,
                                "duration": duration_delta,
                                "difficulty": difficulty,
                                "publisher": publisher,
                            },
                        )

                        if row.get("Genres"):
                            genre_names = [g.strip() for g in row["Genres"].split(",")]
                            for g_name in genre_names:
                                genre, _ = Genre.objects.get_or_create(name=g_name)
                                piece.genres.add(genre)

                        if row.get("Concerts"):
                            concert_names = [
                                g.strip() for g in row["Concerts"].split(",")
                            ]
                            for c_name in concert_names:
                                concert, _ = Concert.objects.get_or_create(title=c_name)
                                piece.concerts.add(concert)

                        if created:
                            created_count += 1
                        else:
                            updated_count += 1

                    messages.success(
                        request,
                        f"Import abgeschlossen: {created_count} Stücke neu angelegt, {updated_count} Stücke aktualisiert.",
                    )
                    return redirect("admin:scorelib_piece_changelist")
            except UnicodeDecodeError:
                messages.error(
                    request,
                    "Fehler: Die Datei konnte nicht gelesen werden. Bitte stellen Sie sicher, dass sie als CSV (UTF-8) gespeichert wurde.",
                )
            except Exception as e:
                messages.error(request, f"Ein unerwarteter Fehler ist aufgetreten: {e}")
    else:
        form = CSVPiecesImportForm()

    return render(request, "admin/csv_pieces_import.html", {"form": form})


@login_required
@transaction.atomic
def import_musicians(request):
    if not request.user.is_staff:
        return redirect("scorelib_index")

    available_groups = InstrumentGroup.objects.all().order_by("name")
    group_names_set = {g.name.lower(): g for g in available_groups}

    if request.method == "POST":
        form = CSVUserImportForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES["csv_file"]
            is_dry_run = form.cleaned_data.get("dry_run")

            try:
                data_set = csv_file.read().decode("utf-8-sig")
                io_string = io.StringIO(data_set)
                reader = csv.DictReader(io_string, delimiter=";")
            except Exception as e:
                messages.error(request, f"Datei konnte nicht gelesen werden: {e}")
                return redirect("import_musicians")

            import_results = []
            sid = transaction.savepoint()

            try:
                for line_num, row in enumerate(reader, start=2):
                    try:
                        first_name = row.get("FirstName").strip()
                        last_name = row.get("LastName").strip()
                        groups_raw = row.get("Instruments").strip()
                    except Exception:
                        import_results.append(
                            {
                                "line": line_num,
                                "name": "Unvollständig",
                                "status": "Fehler: Mind. 'FirstName', 'LastName', 'Instruments' nötig",
                                "type": "danger",
                            }
                        )
                        continue

                    groups_final = ""
                    email_raw = row.get("Email")
                    email = email_raw.strip() if email_raw else ""
                    username = slugify(f"{first_name} {last_name}")
                    raw_password = f"SKG-{last_name.replace(' ', '')}"

                    target_groups = [
                        g.strip() for g in groups_raw.split(",") if g.strip()
                    ]
                    valid_groups = []
                    unknown_groups = []

                    for g_name in target_groups:
                        if g_name.lower() in group_names_set:
                            valid_groups.append(group_names_set[g_name.lower()])
                        else:
                            found = False
                            for group_obj in available_groups:
                                if group_obj.matches_part(g_name):
                                    valid_groups.append(group_obj)
                                    found = True
                                    break
                            if not found:
                                unknown_groups.append(g_name)

                    row_sid = transaction.savepoint()

                    try:
                        user, created = User.objects.get_or_create(
                            username=username,
                            defaults={
                                "first_name": first_name,
                                "last_name": last_name,
                                "email": email,
                            },
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

                        profile, _ = MusicianProfile.objects.get_or_create(user=user)

                        if valid_groups:
                            profile.instrument_groups.set(valid_groups)
                            groups_final = ", ".join(g.name for g in valid_groups)

                        if unknown_groups:
                            status_text += (
                                f" | Unbekannte Gruppen: {', '.join(unknown_groups)}"
                            )
                            row_type = "warning"

                        transaction.savepoint_commit(row_sid)

                    except Exception as e:
                        transaction.savepoint_rollback(row_sid)
                        status_text = f"Kritischer Fehler: {str(e)}"
                        row_type = "danger"
                        raw_password = "-"

                    import_results.append(
                        {
                            "line": line_num,
                            "name": f"{first_name} {last_name}",
                            "email": email,
                            "username": username,
                            "password": raw_password,
                            "instrument_groups": groups_final,
                            "status": status_text,
                            "type": row_type,
                        }
                    )

                if is_dry_run:
                    transaction.savepoint_rollback(sid)
                else:
                    transaction.savepoint_commit(sid)

                return render(
                    request,
                    "admin/csv_user_import_results.html",
                    {
                        "results": import_results,
                        "is_dry_run": is_dry_run,
                        "title": "Import Ergebnis",
                    },
                )

            except Exception as e:
                transaction.savepoint_rollback(sid)
                messages.error(request, f"Allgemeiner Fehler beim Import: {e}")
                return redirect("import_musicians")
    else:
        form = CSVUserImportForm()

    return render(
        request,
        "admin/csv_user_import.html",
        {"form": form, "title": "Musiker-Import", "available_groups": available_groups},
    )


@login_required
def export_import_results_csv(request):
    if not request.user.is_staff:
        return redirect("scorelib_index")

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="musiker_zugangsdaten.csv"'

    writer = csv.writer(response, delimiter=";")
    writer.writerow(
        ["Name", "Email", "Username", "InitialPassword", "InstrumentGroups", "Status"]
    )

    names = request.POST.getlist("name[]")
    emails = request.POST.getlist("email[]")
    usernames = request.POST.getlist("username[]")
    passwords = request.POST.getlist("password[]")
    instrument_groups = request.POST.getlist("instrument_groups[]")
    statuses = request.POST.getlist("status[]")

    for n, e, u, p, i, s in zip(
        names, emails, usernames, passwords, instrument_groups, statuses
    ):
        writer.writerow([n, e, u, p, i, s])

    return response
