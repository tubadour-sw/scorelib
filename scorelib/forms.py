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
    csv_file = forms.FileField(label="Select CSV file")

class CSVUserImportForm(forms.Form):
    csv_file = forms.FileField(label="Select CSV file")
    dry_run = forms.BooleanField(
        required=False, 
        initial=True, 
        label="Dry Run (Check errors only, no save)"
    )

class UserProfileUpdateForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})
    class Meta:
        model = User
        fields = ['username', 'email']
        help_texts = {
            'username': 'Your login name. It may only contain letters, numbers and @/./+/-/_.',
        }

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.exclude(pk=self.instance.pk).filter(username=username).exists():
            raise forms.ValidationError("This username is already taken.")
        return username
        