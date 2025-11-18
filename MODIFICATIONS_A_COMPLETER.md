# 🚀 MODIFICATIONS À COMPLÉTER - TS AIR CARGO

## ✅ DÉJÀ FAIT

1. **Modèle ShippingPrice modifié** ✅
   - Ajout `prix_par_piece`
   - Ajout `type_transport` 
   - Ajout `type_colis`
   - Méthode `calculer_prix()` mise à jour
   - Migration créée ET APPLIQUÉE

2. **Modèle Colis modifié** ✅
   - Ajout `type_colis` (standard/telephone/electronique)
   - Ajout `quantite_pieces` (default=1)
   - Migration créée ET APPLIQUÉE

3. **Calcul prix adapté** ✅
   - Méthode `calculer_prix_automatique()` complète
   - Recherche tarifs dans ShippingPrice
   - Support tarif à la pièce

4. **Formulaire ColisForm modifié** ✅
   - Champs ajoutés: type_colis, quantite_pieces
   - Widgets et labels configurés

---

## 📋 ÉTAPES RESTANTES

### **ÉTAPES 3-5 : DÉJÀ COMPLÉTÉES** ✅

Les modifications des modèles et du calcul de prix sont déjà appliquées.

---

### **ÉTAPE 6 : Modifier formulaire création colis (EN COURS)**

**Fichier : `agent_chine_app/models.py` - Méthode `calculer_prix_automatique()`**

Remplacer la méthode complète (lignes 339-391) par :

```python
def calculer_prix_automatique(self):
    """
    Calculer le prix automatiquement selon les tarifs configurés
    Support : Poids (Cargo/Express), Volume (Bateau), Pièce (Téléphone/Électronique)
    """
    try:
        from reporting_app.models import ShippingPrice
        
        # PRIORITÉ 1 : Tarif à la pièce (téléphone/électronique)
        if self.type_transport in ['cargo', 'express'] and self.type_colis != 'standard':
            # Chercher tarif spécifique pour ce type de colis
            tarif_piece = ShippingPrice.objects.filter(
                actif=True,
                methode_calcul='par_piece',
                type_transport__in=[self.type_transport, 'all'],
                type_colis__in=[self.type_colis, 'all'],
                pays_destination__in=[self.client.pays, 'ALL']
            ).first()
            
            if tarif_piece and tarif_piece.prix_par_piece:
                prix = tarif_piece.prix_par_piece * self.quantite_pieces
                return max(prix, 1000)  # Minimum 1000 FCFA
        
        # PRIORITÉ 2 : Tarif au kilo (standard)
        if self.type_transport in ['cargo', 'express']:
            tarifs = ShippingPrice.objects.filter(
                actif=True,
                methode_calcul='par_kilo',
                type_transport__in=[self.type_transport, 'all'],
                pays_destination__in=[self.client.pays, 'ALL']
            )
            
            for tarif in tarifs:
                prix_calcule = tarif.calculer_prix(float(self.poids), self.volume_m3())
                if prix_calcule > 0:
                    return max(prix_calcule, 1000)
            
            # Prix par défaut si aucun tarif
            multiplier = 12000 if self.type_transport == 'express' else 10000
            return float(self.poids) * multiplier
        
        # PRIORITÉ 3 : Tarif au volume (bateau)
        else:  # bateau
            tarifs = ShippingPrice.objects.filter(
                actif=True,
                methode_calcul='par_metre_cube',
                type_transport__in=['bateau', 'all'],
                pays_destination__in=[self.client.pays, 'ALL']
            )
            
            for tarif in tarifs:
                prix_calcule = tarif.calculer_prix(float(self.poids), self.volume_m3())
                if prix_calcule > 0:
                    return max(prix_calcule, 1000)
            
            # Prix par défaut
            return self.volume_m3() * 300000
        
    except Exception as e:
        # Fallback en cas d'erreur
        if self.type_transport in ['cargo', 'express']:
            if self.type_colis == 'telephone':
                return 5000 * self.quantite_pieces
            elif self.type_colis == 'electronique':
                return 3000 * self.quantite_pieces
            else:
                return float(self.poids) * 10000
        else:
            return self.volume_m3() * 300000
```

---

### **ÉTAPE 6 : Modifier formulaire création colis**

**Fichier : `agent_chine_app/forms.py`**

Ajouter dans le formulaire ColisForm :

```python
type_colis = forms.ChoiceField(
    choices=Colis.TYPE_COLIS_CHOICES,
    initial='standard',
    required=False,
    widget=forms.Select(attrs={'class': 'form-control'})
)

quantite_pieces = forms.IntegerField(
    initial=1,
    min_value=1,
    required=False,
    widget=forms.NumberInput(attrs={'class': 'form-control'})
)
```

**Fichier : `agent_chine_app/templates/agent_chine_app/colis_form.html`**

Ajouter après le champ `type_transport` :

```html
<!-- Type de colis (visible uniquement pour Cargo/Express) -->
<div class="mb-3" id="type_colis_group" style="display: none;">
    <label class="form-label">Type de colis</label>
    {{ form.type_colis }}
    <small class="text-muted">Choisir 'Téléphone' ou 'Électronique' pour tarif à la pièce</small>
</div>

<!-- Quantité de pièces (visible si téléphone/électronique) -->
<div class="mb-3" id="quantite_pieces_group" style="display: none;">
    <label class="form-label">Nombre de pièces</label>
    {{ form.quantite_pieces }}
    <small class="text-muted">Nombre d'appareils dans ce colis</small>
</div>

<script>
// Affichage conditionnel
document.getElementById('id_type_transport').addEventListener('change', function() {
    const typeTransport = this.value;
    const typeColisGroup = document.getElementById('type_colis_group');
    
    if (typeTransport === 'cargo' || typeTransport === 'express') {
        typeColisGroup.style.display = 'block';
    } else {
        typeColisGroup.style.display = 'none';
        document.getElementById('id_type_colis').value = 'standard';
    }
});

document.getElementById('id_type_colis').addEventListener('change', function() {
    const typeColis = this.value;
    const quantiteGroup = document.getElementById('quantite_pieces_group');
    const poidsGroup = document.querySelector('[for="id_poids"]').parentElement;
    
    if (typeColis === 'telephone' || typeColis === 'electronique') {
        quantiteGroup.style.display = 'block';
        poidsGroup.querySelector('input').required = false;
    } else {
        quantiteGroup.style.display = 'none';
        poidsGroup.querySelector('input').required = true;
    }
});
</script>
```

---

### **ÉTAPE 7 : Créer vue PDF Rapport Journalier**

**Fichier : `agent_mali_app/views.py`**

Ajouter après la vue `rapport_journalier_view` :

```python
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from io import BytesIO

@agent_mali_required
def generer_pdf_rapport_journalier(request):
    """
    Génère un PDF professionnel du rapport journalier
    """
    # Récupérer la date
    date_str = request.GET.get('date')
    if date_str:
        try:
            date_rapport = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            date_rapport = date.today()
    else:
        date_rapport = date.today()
    
    # === RÉCUPÉRATION DES DONNÉES (même code que rapport_journalier_view) ===
    colis_receptionnes = Colis.objects.filter(
        statut='arrive',
        lot__date_arrivee__date=date_rapport
    ).select_related('client__user', 'lot')
    
    nb_colis_receptionnes = colis_receptionnes.count()
    valeur_colis_receptionnes = sum(float(c.prix_calcule or 0) for c in colis_receptionnes)
    
    livraisons_jour = Livraison.objects.filter(
        date_livraison_effective__date=date_rapport,
        statut='livree'
    ).select_related('colis__client__user', 'agent_livreur')
    
    nb_colis_livres = livraisons_jour.count()
    
    revenus_jour = livraisons_jour.filter(
        montant_collecte__isnull=False
    ).aggregate(total=Sum('montant_collecte'))['total'] or 0
    revenus_jour = float(revenus_jour)
    
    depenses_jour = Depense.objects.filter(date_depense=date_rapport).select_related('agent')
    total_depenses = depenses_jour.aggregate(total=Sum('montant'))['total'] or 0
    total_depenses = float(total_depenses)
    
    depenses_par_type = depenses_jour.values('type_depense').annotate(
        total=Sum('montant')
    ).order_by('-total')
    
    benefice_net = revenus_jour - total_depenses
    
    colis_en_attente = Colis.objects.filter(statut='arrive').count()
    lots_en_cours = Lot.objects.filter(statut__in=['en_transit', 'expedie', 'arrive']).count()
    
    # === GÉNÉRATION DU PDF ===
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#22c55e'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    # En-tête
    elements.append(Paragraph("TS AIR CARGO MALI", title_style))
    elements.append(Paragraph(f"RAPPORT JOURNALIER D'ACTIVITÉ", styles['Heading2']))
    elements.append(Paragraph(f"Date: {date_rapport.strftime('%d/%m/%Y')}", styles['Normal']))
    elements.append(Paragraph(f"Agent: {request.user.get_full_name()}", styles['Normal']))
    elements.append(Paragraph(f"Généré le: {timezone.now().strftime('%d/%m/%Y à %H:%M')}", styles['Normal']))
    elements.append(Spacer(1, 0.5*cm))
    
    # Section 1: Statistiques
    elements.append(Paragraph("I. STATISTIQUES GLOBALES", styles['Heading3']))
    stats_data = [
        ['Indicateur', 'Valeur'],
        ['Colis réceptionnés', f"{nb_colis_receptionnes}"],
        ['Valeur totale reçue', f"{valeur_colis_receptionnes:,.0f} FCFA"],
        ['Colis livrés', f"{nb_colis_livres}"],
        ['Colis en attente', f"{colis_en_attente}"],
        ['Lots en cours', f"{lots_en_cours}"],
    ]
    
    stats_table = Table(stats_data, colWidths=[10*cm, 6*cm])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#22c55e')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 12),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('BACKGROUND', (0,1), (-1,-1), colors.beige),
        ('GRID', (0,0), (-1,-1), 1, colors.black)
    ]))
    elements.append(stats_table)
    elements.append(Spacer(1, 0.5*cm))
    
    # Section 2: Bilan financier
    elements.append(Paragraph("II. BILAN FINANCIER", styles['Heading3']))
    finance_data = [
        ['REVENUS (Ventes du jour)', f"{revenus_jour:,.0f} FCFA"],
        ['DÉPENSES totales', f"{total_depenses:,.0f} FCFA"],
        ['BÉNÉFICE NET', f"{benefice_net:,.0f} FCFA"],
    ]
    
    finance_table = Table(finance_data, colWidths=[10*cm, 6*cm])
    benefice_color = colors.green if benefice_net >= 0 else colors.red
    finance_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,1), colors.HexColor('#f3f4f6')),
        ('BACKGROUND', (0,2), (0,2), colors.HexColor('#f3f4f6')),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('FONTNAME', (0,2), (-1,2), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0,2), (-1,2), benefice_color),
        ('FONTSIZE', (0,2), (-1,2), 14),
        ('GRID', (0,0), (-1,-1), 1, colors.black)
    ]))
    elements.append(finance_table)
    elements.append(Spacer(1, 0.5*cm))
    
    # Section 3: Dépenses par type
    if depenses_par_type:
        elements.append(Paragraph("III. DÉTAIL DES DÉPENSES", styles['Heading3']))
        depenses_data = [['Type de dépense', 'Montant (FCFA)', 'Pourcentage']]
        
        for dep in depenses_par_type:
            type_display = dict(Depense.TYPE_DEPENSE_CHOICES).get(dep['type_depense'], dep['type_depense'])
            montant = float(dep['total'])
            pourcentage = (montant / total_depenses * 100) if total_depenses > 0 else 0
            depenses_data.append([
                type_display,
                f"{montant:,.0f}",
                f"{pourcentage:.1f}%"
            ])
        
        depenses_data.append(['TOTAL', f"{total_depenses:,.0f}", '100.0%'])
        
        depenses_table = Table(depenses_data, colWidths=[8*cm, 5*cm, 3*cm])
        depenses_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#ef4444')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (1,0), (-1,-1), 'RIGHT'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
            ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#fee2e2')),
            ('GRID', (0,0), (-1,-1), 1, colors.black)
        ]))
        elements.append(depenses_table)
        elements.append(Spacer(1, 0.5*cm))
    
    # Section 4: Colis réceptionnés
    if nb_colis_receptionnes > 0:
        elements.append(Paragraph("IV. COLIS RÉCEPTIONNÉS", styles['Heading3']))
        recept_data = [['N° Suivi', 'Client', 'Valeur (FCFA)']]
        
        for colis in colis_receptionnes[:20]:  # Limiter à 20
            recept_data.append([
                colis.numero_suivi,
                colis.client.user.get_full_name()[:30],
                f"{colis.prix_calcule:,.0f}"
            ])
        
        recept_table = Table(recept_data, colWidths=[4*cm, 8*cm, 4*cm])
        recept_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#3b82f6')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (2,0), (2,-1), 'RIGHT'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('FONTSIZE', (0,1), (-1,-1), 9)
        ]))
        elements.append(recept_table)
        
        if nb_colis_receptionnes > 20:
            elements.append(Paragraph(f"... et {nb_colis_receptionnes - 20} autres colis", styles['Normal']))
        elements.append(Spacer(1, 0.5*cm))
    
    # Section 5: Colis livrés
    if nb_colis_livres > 0:
        elements.append(Paragraph("V. COLIS LIVRÉS", styles['Heading3']))
        livr_data = [['N° Suivi', 'Destinataire', 'Montant (FCFA)']]
        
        for livraison in livraisons_jour[:20]:
            livr_data.append([
                livraison.colis.numero_suivi,
                livraison.nom_destinataire[:30],
                f"{livraison.montant_collecte or 0:,.0f}"
            ])
        
        livr_table = Table(livr_data, colWidths=[4*cm, 8*cm, 4*cm])
        livr_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#10b981')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (2,0), (2,-1), 'RIGHT'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('FONTSIZE', (0,1), (-1,-1), 9)
        ]))
        elements.append(livr_table)
        
        if nb_colis_livres > 20:
            elements.append(Paragraph(f"... et {nb_colis_livres - 20} autres livraisons", styles['Normal']))
    
    # Pied de page
    elements.append(Spacer(1, 1*cm))
    elements.append(Paragraph("_" * 80, styles['Normal']))
    elements.append(Paragraph("TS Air Cargo Mali - Document Confidentiel", 
                             ParagraphStyle('Footer', parent=styles['Normal'], alignment=TA_CENTER)))
    
    # Construire le PDF
    doc.build(elements)
    buffer.seek(0)
    
    # Retourner la réponse
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="rapport_journalier_{date_rapport.strftime("%Y%m%d")}.pdf"'
    
    return response
```

---

### **ÉTAPE 8 : Ajouter route PDF**

**Fichier : `agent_mali_app/urls.py`**

Ajouter dans urlpatterns :

```python
path('rapport-journalier/pdf/', views.generer_pdf_rapport_journalier, name='rapport_journalier_pdf'),
```

---

### **ÉTAPE 9 : Modifier bouton**

**Fichier : `agent_mali_app/templates/agent_mali_app/rapport_journalier.html`**

Remplacer ligne 86-88 :

```html
<a href="{% url 'agent_mali:rapport_journalier_pdf' %}?date={{ date_rapport|date:'Y-m-d' }}" 
   class="btn btn-danger" target="_blank">
    <i class="bi bi-file-earmark-pdf"></i> Télécharger PDF
</a>
```

---

## 🎯 COMMANDES À EXÉCUTER

```bash
# 1. Migrer la base de données
python manage.py migrate

# 2. Créer des tarifs de test dans l'admin Django
# Exemple : Tarif Téléphone Cargo = 5000 FCFA/pièce

# 3. Tester la création d'un colis téléphone
# Choisir Cargo/Express → Type: Téléphone → Quantité: 2

# 4. Vérifier le calcul de prix automatique

# 5. Générer un rapport PDF
```

---

## 📝 NOTES IMPORTANTES

1. **Tarifs par défaut** : Les admins doivent créer des tarifs "Par Pièce" dans l'admin
2. **Migration des données** : Tous les colis existants seront "standard" par défaut
3. **Tests requis** : Tester chaque type de colis avant prod
4. **PDF** : Nécessite ReportLab installé (`pip install reportlab`)

---

## 🔧 DÉPANNAGE

**Erreur "No module reportlab"** :
```bash
pip install reportlab
```

**Erreur migration** :
```bash
python manage.py makemigrations
python manage.py migrate --run-syncdb
```

**Prix incorrect** :
Vérifier que des tarifs existent dans l'admin pour le bon type_transport + type_colis
