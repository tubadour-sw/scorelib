from django import forms
from .models import Composer, Arranger, Concert

class PartSplitEntryForm(forms.Form):
    part_name = forms.CharField(
        max_length=100, 
        widget=forms.TextInput(attrs={'placeholder': 'e.g. Trumpet 1'})
    )
    pages = forms.CharField(
        max_length=50, 
        widget=forms.TextInput(attrs={'placeholder': 'e.g. 1, 3-5'})
    )

# This allows us to have multiple rows in the admin view
PartSplitFormSet = forms.formset_factory(PartSplitEntryForm, extra=1)

class CSVPiecesImportForm(forms.Form):
    csv_file = forms.FileField(label="CSV-Datei auswählen")

class CSVUserImportForm(forms.Form):
    csv_file = forms.FileField(label="CSV-Datei auswählen")
    dry_run = forms.BooleanField(
        required=False, 
        initial=True, 
        label="Dry Run (Nur Fehlerprüfung, keine Speicherung)"
    )
