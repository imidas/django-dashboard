from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.validators import FileExtensionValidator
from django.forms import ModelForm
from django.contrib.auth.models import Group, User
from django.contrib.admin.widgets import FilteredSelectMultiple

from .models import Account
from localflavor.us.forms import USStateField
import re

class SignupForm(UserCreationForm):
    email = forms.EmailField(max_length=200, help_text='Required')
    class Meta:
        model = Account
        fields = ('username', 'email', 'password1', 'password2')


class LoginForm(forms.Form):
    email = forms.CharField(label='email', max_length=100, required=True)
    password = forms.CharField(label='password', required=True, widget=forms.PasswordInput)


class UserSettingsForm(forms.Form):
    business_name = forms.CharField(label='business name', max_length=256, required=True)
    address1 = forms.CharField(max_length=254)
    address2 = forms.CharField(max_length=100, required=False)
    zip_code = forms.CharField(max_length=12)
    state = USStateField()
    city = forms.CharField(max_length=254)
    # country = CountryField(default='US').formfield()
    dark_brand_logo = forms.ImageField(label='dark_brand_logo', widget=forms.FileInput(), required=False)
    light_brand_logo = forms.ImageField(label='light_brand_logo', widget=forms.FileInput(), required=False)
    description = forms.CharField(label='business description', widget=forms.Textarea(attrs={'width':"100%", 'cols' : "80", 'rows': "3", }))
    coupon_description = forms.CharField(label='coupon offer', widget=forms.Textarea(attrs={'width':"100%", 'cols' : "80", 'rows': "3", }))
    first_insert = forms.FileField(validators=[FileExtensionValidator(allowed_extensions=['jpg', 'png', 'mp4'])],
                                       widget=forms.FileInput(), required=False)
    first_insert_audio = forms.FileField(widget=forms.FileInput(), required=False)
    second_insert = forms.FileField(validators=[FileExtensionValidator(allowed_extensions=['jpg', 'png', 'mp4'])],
                                        widget=forms.FileInput(), required=False)
    second_insert_audio = forms.FileField(widget=forms.FileInput(), required=False)


class ManageCampaignForm(forms.Form):
    video_url = forms.CharField(label='video url', max_length=1024, required=True)
    coupon_url = forms.CharField(label='coupon url', max_length=1024, required=True)
    social_network = forms.CharField(label='social_network', widget=forms.HiddenInput(), required=True)


class UploadVideoForm(forms.Form):
    video = forms.FileField(label="content", validators=[FileExtensionValidator(allowed_extensions=['mp4'])],
                              widget=forms.FileInput())
    first_insert_img = forms.FileField(validators=[FileExtensionValidator(allowed_extensions=['jpg', 'png', 'mp4'])],
                              widget=forms.FileInput(), required=False)
    first_insert_audio = forms.FileField(widget=forms.FileInput(), required=False)
    second_insert_img = forms.FileField(validators=[FileExtensionValidator(allowed_extensions=['jpg', 'png', 'mp4'])],
                                        widget=forms.FileInput(), required=False)
    second_insert_audio = forms.FileField(widget=forms.FileInput(), required=False)
    logo = forms.ImageField(validators=[FileExtensionValidator(allowed_extensions=['jpg', 'png'])],
                                        widget=forms.FileInput(), required=False)
    first_insert_time = forms.CharField(max_length=100, required=False)
    output_width = forms.IntegerField(initial=1920)
    output_height = forms.IntegerField(initial=1080)
    logo_placement = forms.CharField(max_length=100, required=True)

    def clean_first_insert_time(self):
        timestamp_pattern = r"^\d{1,2}(:\d{1,2}(:\d{1,2})?(:\d{1,2})?)?$"
        data = self.cleaned_data['first_insert_time']
        data = data.strip()
        if len(data) > 0 and re.match(timestamp_pattern, data) is None:
            raise forms.ValidationError("Insert time format should be hours:minutes:seconds:frames")
        return data


# Create ModelForm based on the Group model.
class GroupAdminForm(forms.ModelForm):
    class Meta:
        model = Group
        exclude = []

    # Add the users field.
    users = forms.ModelMultipleChoiceField(
         queryset=Account.objects.all(),
         required=False,
         # Use the pretty 'filter_horizontal widget'.
         widget=FilteredSelectMultiple('users', False)
    )

    def __init__(self, *args, **kwargs):
        # Do the normal form initialisation.
        super(GroupAdminForm, self).__init__(*args, **kwargs)
        # If it is an existing group (saved objects have a pk).
        if self.instance.pk:
            # Populate the users field with the current Group users.
            self.fields['users'].initial = self.instance.user_set.all()

    def save_m2m(self):
        # Add the users to the Group.
        self.instance.user_set.set(self.cleaned_data['users'])

    def save(self, *args, **kwargs):
        # Default save
        instance = super(GroupAdminForm, self).save()
        # Save many-to-many data
        self.save_m2m()
        return instance