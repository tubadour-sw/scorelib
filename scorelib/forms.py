from django import forms
from .models import Composer, Arranger, Concert
from django.contrib.auth.models import User

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

class UserProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'email']
        help_texts = {
            'username': 'Dein Anmeldename. Er darf nur Buchstaben, Zahlen und @/./+/-/_ enthalten.',
        }

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.exclude(pk=self.instance.pk).filter(username=username).exists():
            raise forms.ValidationError("Dieser Benutzername ist leider schon vergeben.")
        return username
        