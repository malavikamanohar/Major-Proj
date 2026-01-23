"""
Forms for patient data input and authentication
"""
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Patient, Vitals, Labs, UserProfile


class RegistrationForm(UserCreationForm):
    """User registration form with profile fields"""
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'Email address'}))
    first_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'First name'}))
    last_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Last name'}))
    role = forms.ChoiceField(choices=UserProfile.ROLE_CHOICES, required=True, widget=forms.Select(attrs={'class': 'form-select'}))
    department = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Department (optional)'}))
    license_number = forms.CharField(max_length=50, required=False, widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Medical license (for doctors)'}))

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password1', 'password2']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Username'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({'class': 'form-input', 'placeholder': 'Password'})
        self.fields['password2'].widget.attrs.update({'class': 'form-input', 'placeholder': 'Confirm password'})

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        
        if commit:
            user.save()
            UserProfile.objects.create(
                user=user,
                role=self.cleaned_data['role'],
                department=self.cleaned_data.get('department', ''),
                license_number=self.cleaned_data.get('license_number', '')
            )
        return user


class LoginForm(forms.Form):
    """Simple login form"""
    username = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Username'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Password'}))


class PatientForm(forms.ModelForm):
    """Form for patient demographic and clinical data"""
    
    class Meta:
        model = Patient
        fields = [
            'patient_id', 'age', 'sex', 'chief_complaint', 
            'symptoms', 'past_medical_history', 'medications', 'clinical_notes'
        ]
        widgets = {
            'patient_id': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g., PT-2026-001'
            }),
            'age': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': 'Age in years'
            }),
            'sex': forms.Select(attrs={
                'class': 'form-select'
            }),
            'chief_complaint': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 3,
                'placeholder': 'Main reason for visit'
            }),
            'symptoms': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 4,
                'placeholder': 'Describe all symptoms in detail'
            }),
            'past_medical_history': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 3,
                'placeholder': 'Previous conditions, surgeries, etc.'
            }),
            'medications': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 3,
                'placeholder': 'Current medications and dosages'
            }),
            'clinical_notes': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 4,
                'placeholder': 'Additional clinical observations'
            }),
        }


class VitalsForm(forms.ModelForm):
    """Form for vital signs"""
    
    class Meta:
        model = Vitals
        fields = [
            'blood_pressure_systolic', 'blood_pressure_diastolic',
            'heart_rate', 'respiratory_rate', 'oxygen_saturation', 'temperature'
        ]
        widgets = {
            'blood_pressure_systolic': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': 'Systolic (mmHg)'
            }),
            'blood_pressure_diastolic': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': 'Diastolic (mmHg)'
            }),
            'heart_rate': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': 'HR (bpm)'
            }),
            'respiratory_rate': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': 'RR (breaths/min)'
            }),
            'oxygen_saturation': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': 'SpO2 (%)',
                'step': '0.1'
            }),
            'temperature': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': 'Temp (°F)',
                'step': '0.1'
            }),
        }


class LabsForm(forms.ModelForm):
    """Form for laboratory results"""
    
    class Meta:
        model = Labs
        fields = ['lab_results']
        widgets = {
            'lab_results': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 6,
                'placeholder': 'Enter lab results (e.g., WBC: 12.5, Hgb: 14.2, etc.)'
            }),
        }


class FollowUpForm(forms.ModelForm):
    """Simplified form for follow-up visits - only current visit data"""
    
    class Meta:
        model = Patient
        fields = ['chief_complaint', 'symptoms', 'clinical_notes']
        widgets = {
            'chief_complaint': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 3,
                'placeholder': 'Current reason for this follow-up visit'
            }),
            'symptoms': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 4,
                'placeholder': 'Current symptoms at this visit'
            }),
            'clinical_notes': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 4,
                'placeholder': 'Clinical observations for this visit'
            }),
        }
