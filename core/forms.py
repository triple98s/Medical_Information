# core/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model
from .models import PlantHistory, Message, MedicinalPlant

User = get_user_model()

class RegisterForm(forms.ModelForm):
    GENDER_CHOICES = [
        ('', 'Select Gender'),
        ('M', 'Male'),
        ('F', 'Female'),
    ]
    password1 = forms.CharField(required=True)
    password2 = forms.CharField(required=True)
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'placeholder': 'Enter email'}))
    first_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'placeholder': 'Enter first name'}))
    last_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'placeholder': 'Enter last name'}))
    phone = forms.CharField(max_length=20, required=True, widget=forms.TextInput(attrs={'placeholder': 'Enter phone number'}))
    gender = forms.ChoiceField(choices=GENDER_CHOICES, required=True, widget=forms.Select(attrs={'class': 'input_group'}))
    address = forms.CharField(required=True, widget=forms.TextInput(attrs={'placeholder': 'Enter address'}))

    class Meta:
        model = User
        fields = ("email", "first_name", "last_name", "phone", "gender", "address")

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("User with this email already exists.")
        return email

    def clean_first_name(self):
        first_name = self.cleaned_data.get('first_name')
        if first_name and any(char.isdigit() for char in first_name):
            raise forms.ValidationError("Jina la kwanza halipaswi kuwa na namba.")
        return first_name

    def clean_last_name(self):
        last_name = self.cleaned_data.get('last_name')
        if last_name and any(char.isdigit() for char in last_name):
            raise forms.ValidationError("Jina la mwisho halipaswi kuwa na namba.")
        return last_name

    def clean_address(self):
        address = self.cleaned_data.get('address')
        if address and any(char.isdigit() for char in address):
            raise forms.ValidationError("Anuani haipaswi kuwa na namba.")
        return address

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            phone = phone.replace(' ', '')
            if not phone.startswith('+255') and not phone.startswith('0'):
                raise forms.ValidationError("Namba ya simu inapaswa kuanza na +255 au 0.")
            
            if phone.startswith('+255') and len(phone) != 13:
                raise forms.ValidationError("Namba inayoanza na +255 inapaswa kuwa na tarakimu 13 (k.m. +255712345678).")
                
            if phone.startswith('0') and len(phone) != 10:
                raise forms.ValidationError("Namba inayoanza na 0 inapaswa kuwa na tarakimu 10 (k.m. 0712345678).")
                
            if phone.startswith('+255') and not phone[1:].isdigit():
                raise forms.ValidationError("Namba inapaswa kuwa na tarakimu tupu baada ya +.")
                
            if phone.startswith('0') and not phone.isdigit():
                raise forms.ValidationError("Namba inapaswa kuwa na tarakimu tupu.")
                
        return phone

    def clean_password1(self):
        password1 = self.cleaned_data.get('password1')
        if password1 and len(password1) < 8:
            raise forms.ValidationError("Password is too short. It must contain at least 8 characters.")
        return password1

    def clean_password2(self):
        return self.cleaned_data.get('password2')

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        
        # Clear default errors on password2 to strictly control what shows
        if 'password2' in self._errors:
            del self._errors['password2']

        if password1 and password2:
            if password1 != password2:
                self.add_error('password2', "Password doesn't match.")
            elif len(password2) < 8:
                self.add_error('password2', "Password is too short. It must contain at least 8 characters.")
                
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        # Generate a unique username from email
        base_username = self.cleaned_data["email"].split('@')[0][:20]
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        user.username = username
        
        if commit:
            user.set_password(self.cleaned_data["password1"])
            user.save()
            user.profile.phone = self.cleaned_data["phone"]
            user.profile.gender = self.cleaned_data["gender"]
            user.profile.address = self.cleaned_data["address"]
            user.profile.save()
        return user

class LoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={'placeholder': 'Enter email', 'autofocus': True}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Enter password'}))



class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['subject', 'body']
        widgets = {
            'subject': forms.TextInput(attrs={'placeholder': 'Subject'}),
            'body': forms.Textarea(attrs={'placeholder': 'Your message', 'rows': 4}),
        }

class MedicinalPlantForm(forms.ModelForm):
    class Meta:
        model = MedicinalPlant
        fields = [
            'scientific_name', 'local_name', 'common_name',
            'benefits_en', 'benefits_sw',
            'medicinal_uses_en', 'medicinal_uses_sw',
            'precautions_en', 'precautions_sw'
        ]
        widgets = {
            'scientific_name': forms.TextInput(attrs={'placeholder': 'e.g. Azadirachta indica', 'required': True}),
            'local_name': forms.TextInput(attrs={'placeholder': 'e.g. Mwarobaini', 'required': True}),
            'common_name': forms.TextInput(attrs={'placeholder': 'e.g. Neem', 'required': True}),
            'benefits_en': forms.Textarea(attrs={'placeholder': 'Benefits of the plant in English', 'rows': 3}),
            'benefits_sw': forms.Textarea(attrs={'placeholder': 'Faida za mmea kwa Kiswahili', 'rows': 3}),
            'medicinal_uses_en': forms.Textarea(attrs={'placeholder': 'Medicinal uses in English', 'rows': 3}),
            'medicinal_uses_sw': forms.Textarea(attrs={'placeholder': 'Matibabu au matumizi ya dawa kwa Kiswahili', 'rows': 3}),
            'precautions_en': forms.Textarea(attrs={'placeholder': 'Precautions or side effects in English', 'rows': 3}),
            'precautions_sw': forms.Textarea(attrs={'placeholder': 'Tahadhari au madhara ya dawa kwa Kiswahili', 'rows': 3})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['common_name'].required = True

