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

def process_pdf_split(piece, source_file, formset):
    """
    Takes the uploaded master PDF and creates Part objects based on formset data.
    """
    reader = PdfReader(source_file)
    
    for form in formset:
        if form.cleaned_data.get('part_name') and form.cleaned_data.get('pages'):
            part_name = form.cleaned_data['part_name']
            page_string = form.cleaned_data['pages']
            page_indices = parse_page_ranges(page_string)
            
            writer = PdfWriter()
            for idx in page_indices:
                if idx < len(reader.pages):
                    writer.add_page(reader.pages[idx])
            
            # Write to memory
            buffer = io.BytesIO()
            writer.write(buffer)
            
            # Create Part object (Import here to avoid circular imports)
            from .models import Part
            new_part = Part(piece=piece, part_name=part_name)
            
            # Save file
            filename = f"{piece.title}_{part_name}.pdf".replace(" ", "_")
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