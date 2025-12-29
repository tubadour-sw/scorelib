from django import forms

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