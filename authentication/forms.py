from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
import re


class LoginForm(forms.Form):
    """Custom login form using phone number instead of username"""
    
    phone_number = forms.CharField(
        max_length=15,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your phone number',
            'autofocus': True
        }),
        label='Phone Number'
    )
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your password'
        }),
        label='Password'
    )
    
    def __init__(self, *args, **kwargs):
        # Extract request from kwargs if present
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
    
    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number:
            # Remove any non-digit characters except +
            phone_number = re.sub(r'[^\d+]', '', phone_number)
            
            # Validation pour numéros maliens et chinois
            malian_patterns = [
                r'^\+223[67]\d{7}$',     # +22360123456 ou +22370123456
                r'^223[67]\d{7}$',       # 22360123456 ou 22370123456
                r'^[67]\d{7}$'           # 60123456 ou 70123456
            ]
            
            chinese_patterns = [
                r'^\+861[3-9]\d{9}$',    # +8613800138000
                r'^861[3-9]\d{9}$',      # 8613800138000
                r'^1[3-9]\d{9}$'         # 13800138000
            ]
            
            all_patterns = malian_patterns + chinese_patterns
            is_valid = any(re.match(pattern, phone_number) for pattern in all_patterns)
            
            if not is_valid:
                raise ValidationError('Numéro invalide. Formats acceptés: Mali (+223XXXXXXXX) ou Chine (+86XXXXXXXXXXX)')
        return phone_number
    
    def clean(self):
        cleaned_data = super().clean()
        phone_number = cleaned_data.get('phone_number')
        password = cleaned_data.get('password')
        if phone_number and password:
            # Use phone_number as telephone for authentication (USERNAME_FIELD = 'telephone')
            self.user_cache = authenticate(
                self.request,
                telephone=phone_number,
                password=password
            )
            if self.user_cache is None:
                raise ValidationError('Invalid phone number or password')
            else:
                # Vérifier si l'utilisateur est actif
                if not self.user_cache.is_active:
                    raise ValidationError('This account is inactive.')
        else:
            pass
        
        return cleaned_data


class RegistrationForm(forms.Form):
    """User registration form with phone number, name, and password"""
    
    first_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Entrer votre Prénom'
        }),
        label='First Name'
    )
    
    last_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Entrer votre Nom'
        }),
        label='Last Name'
    )
    
    phone_number = forms.CharField(
        max_length=15,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Entrer votre numéro de téléphone'
        }),
        label='Phone Number'
    )
    
    password1 = forms.CharField(
        min_length=8,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Entrer votre mot de passe'
        }),
        label='Password',
        help_text='Le mot de passe doit être au minimun de 8 caractères'
    )
    
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirmer votre mot de passe'
        }),
        label='Confirm Password'
    )
    
    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number:
            # Remove any non-digit characters except +
            phone_number = re.sub(r'[^\d+]', '', phone_number)
            # Basic phone number validation
            if not re.match(r'^\+?[\d]{10,15}$', phone_number):
                raise ValidationError('Please enter a valid phone number')
            
            # Check if phone number already exists
            from .models import CustomUser
            if CustomUser.objects.filter(telephone=phone_number).exists():
                raise ValidationError('This phone number is already registered')
        
        return phone_number
    
    def clean_first_name(self):
        first_name = self.cleaned_data.get('first_name')
        if first_name:
            # Only allow letters and spaces
            if not re.match(r'^[a-zA-Z\s]+$', first_name):
                raise ValidationError('First name should only contain letters')
        return first_name.title() if first_name else first_name
    
    def clean_last_name(self):
        last_name = self.cleaned_data.get('last_name')
        if last_name:
            # Only allow letters and spaces
            if not re.match(r'^[a-zA-Z\s]+$', last_name):
                raise ValidationError('Last name should only contain letters')
        return last_name.title() if last_name else last_name
    
    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        
        if password1 and password2:
            if password1 != password2:
                raise ValidationError('Passwords do not match')
        
        return cleaned_data
    
    def save(self):
        """Créer un nouvel utilisateur à partir des données du formulaire"""
        from .models import CustomUser
        
        user = CustomUser(
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
            telephone=self.cleaned_data['phone_number'],
            username=self.cleaned_data['phone_number'],  # username = téléphone
            role='client'  # Par défaut, les nouveaux utilisateurs sont des clients
        )
        user.set_password(self.cleaned_data['password1'])
        user.save()
        return user


class OTPVerificationForm(forms.Form):
    """OTP verification form for phone number verification"""
    
    phone_number = forms.CharField(
        max_length=15,
        widget=forms.HiddenInput(),
        required=False
    )
    
    otp_code = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-control text-center',
            'placeholder': 'Enter 6-digit OTP',
            'maxlength': '6',
            'pattern': '[0-9]{6}',
            'autocomplete': 'one-time-code'
        }),
        label='OTP Code',
        help_text='Enter the 6-digit code sent to your phone'
    )
    
    def clean_otp_code(self):
        otp_code = self.cleaned_data.get('otp_code')
        if otp_code:
            if not re.match(r'^\d{6}$', otp_code):
                raise ValidationError('OTP must be a 6-digit number')
        return otp_code
    
    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number:
            # Remove any non-digit characters except +
            phone_number = re.sub(r'[^\d+]', '', phone_number)
            # Basic phone number validation
            if not re.match(r'^\+?[\d]{10,15}$', phone_number):
                raise ValidationError('Please enter a valid phone number')
        return phone_number


class PasswordResetRequestForm(forms.Form):
    """Password reset request form using phone number"""
    
    phone_number = forms.CharField(
        max_length=15,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your registered phone number'
        }),
        label='Phone Number',
        help_text='Enter the phone number associated with your account'
    )
    
    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number:
            # Remove any non-digit characters except +
            phone_number = re.sub(r'[^\d+]', '', phone_number)
            # Basic phone number validation
            if not re.match(r'^\+?[\d]{10,15}$', phone_number):
                raise ValidationError('Please enter a valid phone number')
        
        return phone_number


class PasswordResetForm(forms.Form):
    """Password reset form with OTP verification"""
    
    phone_number = forms.CharField(
        max_length=15,
        widget=forms.HiddenInput()
    )
    
    otp_code = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-control text-center',
            'placeholder': 'Enter 6-digit OTP',
            'maxlength': '6',
            'pattern': '[0-9]{6}',
            'autocomplete': 'one-time-code'
        }),
        label='OTP Code',
        help_text='Enter the 6-digit code sent to your phone'
    )
    
    new_password = forms.CharField(
        min_length=8,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter new password'
        }),
        label='New Password',
        help_text='Password must be at least 8 characters long'
    )
    
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm new password'
        }),
        label='Confirm Password'
    )
    
    def clean_otp_code(self):
        otp_code = self.cleaned_data.get('otp_code')
        if otp_code:
            if not re.match(r'^\d{6}$', otp_code):
                raise ValidationError('OTP must be a 6-digit number')
        return otp_code
    
    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number:
            # Remove any non-digit characters except +
            phone_number = re.sub(r'[^\d+]', '', phone_number)
            # Basic phone number validation
            if not re.match(r'^\+?[\d]{10,15}$', phone_number):
                raise ValidationError('Please enter a valid phone number')
        return phone_number
    
    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if new_password and confirm_password:
            if new_password != confirm_password:
                raise ValidationError('Passwords do not match')
        
        return cleaned_data


class AdminChinaLoginForm(forms.Form):
    """Formulaire de connexion spécifique pour Admin Chine avec support des numéros chinois"""
    
    phone_number = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+86 138 0013 8000 ou 13800138000',
            'autofocus': True
        }),
        label='Numéro de téléphone chinois',
        help_text='Format accepté: +86XXXXXXXXX ou directement XXXXXXXXXXX (11 chiffres)'
    )
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Entrez votre mot de passe'
        }),
        label='Mot de passe'
    )
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
    
    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number:
            
            # Nettoyer le numéro: enlever espaces, tirets, parenthèses
            cleaned_number = re.sub(r'[\s\-\(\)]', '', phone_number)
            
            # Si commence par 86 sans +, ajouter +
            if cleaned_number.startswith('86') and not cleaned_number.startswith('+'):
                cleaned_number = '+' + cleaned_number
            
            # Si commence par 1 et a 11 chiffres, ajouter +86 (format chinois)
            elif re.match(r'^1[3-9]\d{9}$', cleaned_number):
                cleaned_number = '+86' + cleaned_number
            
            # Vérification finale du format
            if cleaned_number.startswith('+86'):
                # Validation stricte pour les numéros chinois
                if not re.match(r'^\+861[3-9]\d{9}$', cleaned_number):
                    raise ValidationError('Numéro chinois invalide. Format attendu: +8613XXXXXXXXX (11 chiffres après +86, commençant par 1)')
            else:
                # Validation générale pour autres pays
                if not re.match(r'^\+?[\d]{10,15}$', cleaned_number):
                    raise ValidationError('Numéro de téléphone invalide')
        
            return cleaned_number
        
        return phone_number
    
    def clean(self):
        cleaned_data = super().clean()
        phone_number = cleaned_data.get('phone_number')
        password = cleaned_data.get('password')
        
        if phone_number and password:
            # Authentifier avec le numéro normalisé
            self.user_cache = authenticate(
                self.request,
                telephone=phone_number,
                password=password
            )
            
            if self.user_cache is None:
                raise ValidationError('Numéro de téléphone ou mot de passe incorrect')
            
            # Vérifier que l'utilisateur est admin Chine
            if not self.user_cache.is_admin_chine:
                raise ValidationError('Accès réservé aux administrateurs Chine')
                
            if not self.user_cache.is_active:
                raise ValidationError('Ce compte est désactivé')
        
        return cleaned_data


class ResendOTPForm(forms.Form):
    """Form to resend OTP to phone number"""
    
    phone_number = forms.CharField(
        max_length=15,
        widget=forms.HiddenInput()
    )
    
    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number:
            # Remove any non-digit characters except +
            phone_number = re.sub(r'[^\d+]', '', phone_number)
            # Basic phone number validation
            if not re.match(r'^\+?[\d]{10,15}$', phone_number):
                raise ValidationError('Please enter a valid phone number')
        return phone_number
