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

import io
import re
import os
import subprocess
import shutil
from pypdf import PdfReader, PdfWriter
from django.core.files.base import ContentFile
from .models import Part, SiteSettings, AudioRecording
from django.conf import settings
from django.utils.text import slugify

def parse_page_ranges(range_string):
    """
    Converts strings like '1, 3-5, 8' into a list of 0-based page indices: [0, 2, 3, 4, 7]
    """
    pages = set()
    # Remove any whitespace
    clean_str = re.sub(r'\s+', '', range_string)
    
    for part in clean_str.split(','):
        if '-' in part:
            try:
                start, end = part.split('-')
                pages.update(range(int(start) - 1, int(end)))
            except ValueError:
                continue
        else:
            try:
                pages.add(int(part) - 1)
            except ValueError:
                continue
    return sorted(list(pages))

def process_pdf_split(piece, source_file, valid_data_list):
    """
    Takes the master PDF and creates Part objects based on the
    filtered list of dictionaries (valid_data_list).
    """
    reader = PdfReader(source_file)
    
    # Since we now get a list of dictionaries, we iterate directly over it
    for entry in valid_data_list:
        # Access via key in dictionary instead of .cleaned_data.get()
        part_name = entry.get('part_name')
        page_string = entry.get('pages')
        
        if part_name and page_string:
            page_indices = parse_page_ranges(page_string)
            
            writer = PdfWriter()
            for idx in page_indices:
                # Ensure the page exists in the source PDF
                if 0 <= idx < len(reader.pages):
                    writer.add_page(reader.pages[idx])
            
            # Only save if pages were added to the PDF
            if len(writer.pages) > 0:
                # Write to memory
                buffer = io.BytesIO()
                writer.write(buffer)
                
                # Create new Part object
                new_part = Part(piece=piece, part_name=part_name)
                
                # Generate filename (clean special characters/spaces)
                safe_title = "".join(x for x in piece.title if x.isalnum() or x in "._- ")
                safe_part = "".join(x for x in part_name if x.isalnum() or x in "._- ")
                filename = f"{safe_title}_{safe_part}-id{piece.id}.pdf".replace(" ", "_")
                
                # Save file
                new_part.pdf_file.save(filename, ContentFile(buffer.getvalue()), save=False)
                new_part.save()
		

def split_pdf_into_parts(piece, source_pdf_file, split_data):
    """
    split_data is a list of dictionaries:
    [{'name': 'Trumpet 1', 'pages': [0, 1]}, {'name': 'Tuba', 'pages': [2]}]
    Page numbers are 0-based.
    """
    reader = PdfReader(source_pdf_file)
    
    for item in split_data:
        writer = PdfWriter()
        for page_num in item['pages']:
            writer.add_page(reader.pages[page_num])
        
        # Write to memory instead of disk
        buffer = io.BytesIO()
        writer.write(buffer)
        
        # Create new 'Part' object
        new_part = Part(
            piece=piece,
            part_name=item['name']
        )
        
        # Attach file to the model
        filename = f"{piece.title}_{item['name']}.pdf".replace(" ", "_")
        new_part.pdf_file.save(filename, ContentFile(buffer.getvalue()), save=False)
        new_part.save()



def process_audio_file_logic(recording_obj):
    """
    Centralized logic for processing an uploaded audio file:
    - If FFmpeg is available and audio ripping is enabled, convert to MP3 with metadata
    - Otherwise, just rename/move the file to a consistent location and naming scheme.
    This function can be called both from the audio ripping workflow and from any future direct uploads of audio files.
    """
    if not recording_obj.audio_file or not os.path.exists(recording_obj.audio_file.path):
        return

    site_settings = SiteSettings.objects.first()
    
    old_full_path = recording_obj.audio_file.path
    ext = os.path.splitext(old_full_path)[1].lower()
    
    # generate a safe filename based on concert title, piece title and description (for distinguishing movements/sätze)
    safe_piece = "".join(x for x in recording_obj.piece.title if x.isalnum() or x in "._- ")
    safe_concert = "".join(x for x in recording_obj.concert.title if x.isalnum() or x in "._- ") 
    # include description but only keep safe characters and limit length to avoid filesystem issues
    safe_desc = "".join(x for x in recording_obj.description if x.isalnum() or x in "._- ")[:20]
    
    base_name = f"{safe_concert}_{safe_piece}_{safe_desc}_c{recording_obj.concert.id}_r{recording_obj.id}"
    
    # case 1: ffmpeg is available and audio ripping is enabled -> convert to MP3 with metadata
    if site_settings and site_settings.audio_ripping_enabled and shutil.which('ffmpeg'):
        new_filename = f"{base_name}.mp3"
        new_rel_path = os.path.join('concerts/audio', new_filename)
        new_full_path = os.path.join(settings.MEDIA_ROOT, new_rel_path)

        if old_full_path == new_full_path and ext == '.mp3':
            return # Bereits korrekt verarbeitet

        cmd = [
            'ffmpeg', '-threads', '1', '-i', old_full_path,
            '-codec:a', 'libmp3lame', '-qscale:a', '6', # good compression
            '-metadata', f'title={recording_obj.piece.title}',
            '-metadata', f'artist={site_settings.band_name}',
            '-metadata', f'album={recording_obj.concert.title}',
            '-metadata', f'date={recording_obj.concert.date.year if recording_obj.concert.date else ""}',
            '-metadata', f'comment={recording_obj.description}', # description in comment tag
            new_full_path, '-y'
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            if old_full_path != new_full_path:
                os.remove(old_full_path)
            
            # update model with new file path and name without signaling
            recording_obj.audio_file.name = new_rel_path
            recording_obj.save(update_fields=['audio_file'])
        except Exception as e:
            print(f"FFmpeg fehlgeschlagen, Fallback zu Rename: {e}")
            rename_only(recording_obj, old_full_path, base_name, ext)
    else:
        # case 2: ffmpeg not available or ripping disabled -> just rename/move the file to a consistent location
        rename_only(recording_obj, old_full_path, base_name, ext)

def rename_only(recording_obj, old_full_path, base_name, ext):
    new_filename = f"{base_name}{ext}"
    new_rel_path = os.path.join('concerts/audio', new_filename)
    new_full_path = os.path.join(settings.MEDIA_ROOT, new_rel_path)

    if old_full_path != new_full_path:
        os.makedirs(os.path.dirname(new_full_path), exist_ok=True)
        shutil.move(old_full_path, new_full_path)
        recording_obj.audio_file.name = new_rel_path
        recording_obj.save(update_fields=['audio_file'])


def get_orphaned_files():
    orphaned_files = []
    
    # Zu prüfende Pfade und deren zugehörige Models
    # Format: (Model, Feldname, Unterordner)
    checks = [
        (Part, 'pdf_file', 'parts'),
        (AudioRecording, 'audio_file', 'concerts/audio'),
    ]

    for model, field, subfolder in checks:
        full_dir_path = os.path.join(settings.MEDIA_ROOT, subfolder)
        if not os.path.exists(full_dir_path):
            continue

        # Datenbank-Bestand als Set für schnellen Abgleich
        files_in_db = set(model.objects.exclude(**{field: ""}).values_list(field, flat=True))

        for root, dirs, files in os.walk(full_dir_path):
            for filename in files:
                # Erstelle den Pfad, wie er in der DB gespeichert wäre (z.B. 'parts/file.pdf')
                rel_path = os.path.relpath(os.path.join(root, filename), settings.MEDIA_ROOT)
                
                if rel_path not in files_in_db:
                    full_file_path = os.path.join(settings.MEDIA_ROOT, rel_path)
                    orphaned_files.append({
                        'path': rel_path,
                        'name': filename,
                        'type': 'PDF (Noten)' if subfolder == 'parts' else 'Audio (Konzert)',
                        'size': os.path.getsize(full_file_path)
                    })
                
    return sorted(orphaned_files, key=lambda x: x['type'])