import io
import re
from pypdf import PdfReader, PdfWriter
from django.core.files.base import ContentFile
from .models import Part

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
    Nimmt das Master-PDF und erstellt Part-Objekte basierend auf der 
    gefilterten Liste von Dictionaries (valid_data_list).
    """
    reader = PdfReader(source_file)
    
    # Da wir nun eine Liste von Dictionaries erhalten, iterieren wir direkt darüber
    for entry in valid_data_list:
        # Zugriff per Key im Dictionary statt .cleaned_data.get()
        part_name = entry.get('part_name')
        page_string = entry.get('pages')
        
        if part_name and page_string:
            page_indices = parse_page_ranges(page_string)
            
            writer = PdfWriter()
            for idx in page_indices:
                # Sicherstellen, dass die Seite im Quell-PDF existiert
                if 0 <= idx < len(reader.pages):
                    writer.add_page(reader.pages[idx])
            
            # Nur speichern, wenn auch Seiten zum PDF hinzugefügt wurden
            if len(writer.pages) > 0:
                # In den Speicher schreiben
                buffer = io.BytesIO()
                writer.write(buffer)
                
                # Neues Part-Objekt erstellen
                new_part = Part(piece=piece, part_name=part_name)
                
                # Dateinamen generieren (Sonderzeichen/Leerzeichen bereinigen)
                safe_title = "".join(x for x in piece.title if x.isalnum() or x in "._- ")
                safe_part = "".join(x for x in part_name if x.isalnum() or x in "._- ")
                filename = f"{safe_title}_{safe_part}.pdf".replace(" ", "_")
                
                # Datei speichern
                new_part.pdf_file.save(filename, ContentFile(buffer.getvalue()), save=False)
                new_part.save()
		

def split_pdf_into_parts(piece, source_pdf_file, split_data):
    """
    split_data ist eine Liste von Dictionaries: 
    [{'name': 'Trompete 1', 'pages': [0, 1]}, {'name': 'Tuba', 'pages': [2]}]
    Dabei sind die Seitenzahlen 0-basiert.
    """
    reader = PdfReader(source_pdf_file)
    
    for item in split_data:
        writer = PdfWriter()
        for page_num in item['pages']:
            writer.add_page(reader.pages[page_num])
        
        # In den Speicher schreiben, statt auf die Festplatte
        buffer = io.BytesIO()
        writer.write(buffer)
        
        # Neues 'Part' Objekt erstellen
        new_part = Part(
            piece=piece,
            part_name=item['name']
        )
        
        # Datei an das Modell hängen
        filename = f"{piece.title}_{item['name']}.pdf".replace(" ", "_")
        new_part.pdf_file.save(filename, ContentFile(buffer.getvalue()), save=False)
        new_part.save()