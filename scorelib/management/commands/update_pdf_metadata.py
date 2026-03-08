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
from django.core.management.base import BaseCommand, CommandError
from django.core.files.base import ContentFile
from pypdf import PdfReader, PdfWriter

from scorelib.models import Part
from scorelib.utils import add_pdf_metadata


class Command(BaseCommand):
    help = 'Update all existing Part PDFs with metadata (title, composer, arranger, part name) for sheet music apps like MobileSheets and forScore'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            dest='dry_run',
            help='Show what would be updated without making changes',
        )
        parser.add_argument(
            '--piece-id',
            type=int,
            dest='piece_id',
            help='Update only parts of a specific piece (by piece ID)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        piece_id = options.get('piece_id')

        # Get all parts, optionally filtered by piece ID
        if piece_id:
            parts = Part.objects.filter(piece_id=piece_id)
        else:
            parts = Part.objects.all()

        parts = parts.exclude(pdf_file='').exclude(pdf_file__isnull=True)
        total_parts = parts.count()

        if total_parts == 0:
            self.stdout.write(self.style.WARNING('No parts with PDF files found.'))
            return

        self.stdout.write(
            self.style.SUCCESS(f'Found {total_parts} parts to update.')
        )

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN: No changes will be made.\n'))

        updated_count = 0
        error_count = 0

        for i, part in enumerate(parts, 1):
            try:
                piece = part.piece
                part_name = part.part_name
                pdf_path = part.pdf_file.path

                if not os.path.exists(pdf_path):
                    self.stdout.write(
                        self.style.ERROR(
                            f'[{i}/{total_parts}] ✗ {piece.title} - {part_name} '
                            f'(PDF file not found: {pdf_path})'
                        )
                    )
                    error_count += 1
                    continue

                # Read the existing PDF
                try:
                    reader = PdfReader(pdf_path)
                    writer = PdfWriter()

                    # Copy all pages
                    for page in reader.pages:
                        writer.add_page(page)

                    # Add metadata
                    add_pdf_metadata(writer, piece, part_name)

                    if dry_run:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'[{i}/{total_parts}] → {piece.title} - {part_name}'
                            )
                        )
                    else:
                        # Write back to the same location
                        import io
                        buffer = io.BytesIO()
                        writer.write(buffer)
                        buffer.seek(0)

                        # Save the updated PDF, keeping the original filename
                        with open(pdf_path, 'wb') as f:
                            f.write(buffer.read())

                        self.stdout.write(
                            self.style.SUCCESS(
                                f'[{i}/{total_parts}] ✓ {piece.title} - {part_name}'
                            )
                        )

                    updated_count += 1

                except Exception as pdf_error:
                    self.stdout.write(
                        self.style.ERROR(
                            f'[{i}/{total_parts}] ✗ {piece.title} - {part_name} '
                            f'(Error reading/writing PDF: {str(pdf_error)})'
                        )
                    )
                    error_count += 1

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'[{i}/{total_parts}] ✗ Unexpected error: {str(e)}'
                    )
                )
                error_count += 1

        # Summary
        self.stdout.write('\n' + '=' * 70)
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(f'DRY RUN SUMMARY: {updated_count} parts would be updated')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'✓ Successfully updated: {updated_count} parts')
            )

        if error_count > 0:
            self.stdout.write(
                self.style.ERROR(f'✗ Errors: {error_count} parts')
            )

        self.stdout.write('=' * 70)
