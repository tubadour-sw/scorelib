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