from django import forms
from django.contrib.auth import get_user_model
from .models import Client, Lot, Colis

User = get_user_model()

class ClientForm(forms.ModelForm):
    """
    Formulaire pour créer/modifier un client
    """
    # Champs pour l'utilisateur
    first_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Prénom'
        }),
        label='Prénom'
    )
    
    last_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nom de famille'
        }),
        label='Nom de famille'
    )
    
    phone_number = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '99281899 ou 22399281899',
        }),
        label='Numéro de téléphone',
        help_text='Format: 99281899 ou 22399281899 (avec ou sans indicatif)'
    )
    
    class Meta:
        model = Client
        fields = ['adresse', 'pays']
        
        widgets = {
            'adresse': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Adresse complète du client'
            }),
            'pays': forms.Select(attrs={
                'class': 'form-select'
            })
        }
        
        labels = {
            'adresse': 'Adresse',
            'pays': 'Pays'
        }
    
    def save(self, commit=True):
        """
        Créer ou mettre à jour le client et l'utilisateur associé
        """
        client = super().save(commit=False)
        
        if client.pk:  # Modification d'un client existant
            user = client.user
            user.first_name = self.cleaned_data['first_name']
            user.last_name = self.cleaned_data['last_name']
            user.phone_number = self.cleaned_data['phone_number']
            if commit:
                user.save()
                client.save()
        else:  # Nouveau client
            # Créer l'utilisateur
            user = User.objects.create(
                first_name=self.cleaned_data['first_name'],
                last_name=self.cleaned_data['last_name'],
                phone_number=self.cleaned_data['phone_number'],
                role='client'
            )
            client.user = user
            if commit:
                client.save()
        
        return client


class LotForm(forms.ModelForm):
    """
    Formulaire pour créer/modifier un lot
    Selon les spécifications du DEVBOOK
    """
    class Meta:
        model = Lot
        fields = ['prix_transport', 'statut']
        
        widgets = {
            'prix_transport': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0'
            }),
            'statut': forms.Select(attrs={
                'class': 'form-select'
            })
        }
        
        labels = {
            'prix_transport': 'Prix de transport (FCFA)',
            'statut': 'Statut du lot'
        }
        
        help_texts = {
            'prix_transport': 'Prix total du transport pour ce lot (optionnel)',
            'statut': 'Le statut sera "Ouvert" par défaut'
        }
    
    def __init__(self, *args, **kwargs):
        self.agent = kwargs.pop('agent', None)
        super().__init__(*args, **kwargs)
        
        # Pour les nouveaux lots, définir le statut par défaut
        if not self.instance.pk:
            self.fields['statut'].initial = 'ouvert'
    
    def save(self, commit=True):
        lot = super().save(commit=False)
        
        # Assigner l'agent créateur pour un nouveau lot
        if not lot.pk and self.agent:
            lot.agent_createur = self.agent
            
        if commit:
            lot.save()
            
        return lot


class ColisForm(forms.ModelForm):
    """
    Formulaire pour créer/modifier un colis avec autocomplétion client
    et affichage conditionnel selon le type de transport
    """
    class Meta:
        model = Colis
        fields = [
            'client', 'lot', 'type_transport', 'image',
            'longueur', 'largeur', 'hauteur', 'poids', 
            'mode_paiement', 'statut', 'description'
        ]
        
        widgets = {
            'client': forms.Select(attrs={
                'class': 'form-select client-select',
                'id': 'id_client',
                'onchange': 'loadClientInfo(this.value)'
            }),
            'lot': forms.Select(attrs={
                'class': 'form-select'
            }),
            'type_transport': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_type_transport',
                'onchange': 'toggleTransportFields()'
            }),
            'image': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'longueur': forms.NumberInput(attrs={
                'class': 'form-control dimension-field',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0'
            }),
            'largeur': forms.NumberInput(attrs={
                'class': 'form-control dimension-field',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0'
            }),
            'hauteur': forms.NumberInput(attrs={
                'class': 'form-control dimension-field',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0'
            }),
            'poids': forms.NumberInput(attrs={
                'class': 'form-control weight-field',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0'
            }),
            'mode_paiement': forms.Select(attrs={
                'class': 'form-select'
            }),
            'statut': forms.Select(attrs={
                'class': 'form-select'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Description du contenu du colis'
            })
        }
        
        labels = {
            'client': 'Client',
            'lot': 'Lot',
            'type_transport': 'Type de transport',
            'image': 'Photo du colis',
            'longueur': 'Longueur (cm)',
            'largeur': 'Largeur (cm)', 
            'hauteur': 'Hauteur (cm)',
            'poids': 'Poids (kg)',
            'mode_paiement': 'Mode de paiement',
            'statut': 'Statut',
            'description': 'Description'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filtrer les lots ouverts seulement pour nouveaux colis
        if not self.instance.pk:
            self.fields['lot'].queryset = Lot.objects.filter(statut='ouvert')
            self.fields['statut'].initial = 'receptionne_chine'
            self.fields['type_transport'].initial = 'cargo'
        
        # Ajouter les attributs d'autocomplétion pour le client
        self.fields['client'].widget.attrs.update({
            'data-live-search': 'true',
            'data-size': '5'
        })
        
        # Rendre l'image obligatoire
        self.fields['image'].required = True


class LotSearchForm(forms.Form):
    """
    Formulaire de recherche pour les lots
    """
    numero_lot = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Numéro de lot'
        }),
        label='Numéro de lot'
    )
    
    statut = forms.ChoiceField(
        choices=[('', 'Tous les statuts')] + Lot.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label='Statut'
    )
    
    date_debut = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label='Date de début'
    )
    
    date_fin = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label='Date de fin'
    )


class ColisSearchForm(forms.Form):
    """
    Formulaire de recherche pour les colis
    """
    numero_suivi = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'TSXXXXXXXX'
        }),
        label='Numéro de suivi'
    )
    
    client = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nom ou téléphone du client'
        }),
        label='Client'
    )
    
    statut = forms.ChoiceField(
        choices=[('', 'Tous les statuts')] + Colis.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label='Statut'
    )
    
    lot = forms.ModelChoiceField(
        queryset=Lot.objects.all(),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label='Lot',
        empty_label='Tous les lots'
    )
