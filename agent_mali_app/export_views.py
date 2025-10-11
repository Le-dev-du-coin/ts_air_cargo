from django.shortcuts import get_object_or_404, HttpResponse
from django.contrib.auth.decorators import login_required
from django.db.models import F, Value, CharField
from django.db.models.functions import Concat
from django.utils import timezone
from django.conf import settings

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

from agent_chine_app.models import Lot, Colis

@login_required
def export_colis_excel(request, lot_id):
    """
    Exporter la liste des colis d'un lot en format Excel
    """
    lot = get_object_or_404(Lot, id=lot_id)
    
    # Récupérer les colis du lot avec les informations nécessaires
    colis_list = Colis.objects.filter(lot=lot).annotate(
        nom_complet=Concat('client__prenom', Value(' '), 'client__nom', 
                          output_field=CharField())
    ).values(
        'code_colis',
        'nom_complet',
        'client__telephone',
        'poids',
        'prix_estime',
        'statut',
        'date_creation',
        'date_mise_a_jour'
    )
    
    # Créer un DataFrame pandas avec les données
    df = pd.DataFrame.from_records(colis_list)
    
    # Renommer les colonnes pour un affichage plus lisible
    df = df.rename(columns={
        'code_colis': 'Code Colis',
        'nom_complet': 'Client',
        'client__telephone': 'Téléphone',
        'poids': 'Poids (kg)',
        'prix_estime': 'Prix (FCFA)',
        'statut': 'Statut',
        'date_creation': 'Date de création',
        'date_mise_a_jour': 'Dernière mise à jour'
    })
    
    # Formater les dates
    df['Date de création'] = pd.to_datetime(df['Date de création']).dt.strftime('%d/%m/%Y %H:%M')
    df['Dernière mise à jour'] = pd.to_datetime(df['Dernière mise à jour']).dt.strftime('%d/%m/%Y %H:%M')
    
    # Créer la réponse HTTP avec le fichier Excel
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="colis_lot_{lot.numero_lot}.xlsx"'
    
    # Créer un writer Excel avec pandas
    with pd.ExcelWriter(response, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Liste des colis', index=False)
        
        # Obtenir le classeur et la feuille de calcul
        workbook = writer.book
        worksheet = writer.sheets['Liste des colis']
        
        # Définir les formats
        header_format = workbook.add_format({
            'bold': True,
            'text_wrap': True,
            'valign': 'top',
            'fg_color': '#4CAF50',
            'color': 'white',
            'border': 1
        })
        
        # Appliquer le format aux en-têtes
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)
        
        # Ajuster la largeur des colonnes
        for i, col in enumerate(df.columns):
            max_length = max(df[col].astype(str).apply(len).max(), len(col)) + 2
            worksheet.set_column(i, i, max_length)
    
    return response

@login_required
def export_colis_pdf(request, lot_id):
    """
    Exporter la liste des colis d'un lot en format PDF
    """
    lot = get_object_or_404(Lot, id=lot_id)
    
    # Récupérer les colis du lot avec les informations nécessaires
    colis_list = Colis.objects.filter(lot=lot).annotate(
        nom_complet=Concat('client__prenom', Value(' '), 'client__nom', 
                          output_field=CharField())
    ).values(
        'code_colis',
        'nom_complet',
        'client__telephone',
        'poids',
        'prix_estime',
        'statut',
    ).order_by('code_colis')
    
    # Créer un objet BytesIO pour le PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="colis_lot_{lot.numero_lot}.pdf"'
    
    # Créer le document PDF
    doc = SimpleDocTemplate(
        response,
        pagesize=letter,
        rightMargin=30, leftMargin=30,
        topMargin=30, bottomMargin=30
    )
    
    # Styles pour le PDF
    styles = getSampleStyleSheet()
    title_style = styles['Heading1']
    
    # Contenu du PDF
    elements = []
    
    # Titre du document
    elements.append(Paragraph(f"Liste des colis - Lot {lot.numero_lot}", title_style))
    elements.append(Spacer(1, 12))
    
    # Informations du lot
    elements.append(Paragraph(f"<b>Date de création :</b> {lot.date_creation.strftime('%d/%m/%Y')}", styles['Normal']))
    elements.append(Paragraph(f"<b>Nombre de colis :</b> {len(colis_list)}", styles['Normal']))
    elements.append(Spacer(1, 12))
    
    # Tableau des colis
    if colis_list:
        # En-têtes du tableau
        data = [
            ['Code', 'Client', 'Téléphone', 'Poids (kg)', 'Prix (FCFA)', 'Statut']
        ]
        
        # Données du tableau
        for colis in colis_list:
            data.append([
                colis['code_colis'],
                colis['nom_complet'],
                colis['client__telephone'],
                f"{colis['poids']:.2f}" if colis['poids'] else 'N/A',
                f"{colis['prix_estime']:,.0f}" if colis['prix_estime'] else 'N/A',
                colis['statut'].capitalize()
            ])
        
        # Créer le tableau
        table = Table(data, colWidths=[1.2*inch, 2*inch, 1.2*inch, 0.8*inch, 1*inch, 1*inch])
        
        # Style du tableau
        style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4CAF50')),  # En-tête vert
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ])
        
        # Alternance des couleurs des lignes
        for i in range(1, len(data)):
            if i % 2 == 0:
                bg_color = colors.HexColor('#F9F9F9')
                style.add('BACKGROUND', (0, i), (-1, i), bg_color)
        
        table.setStyle(style)
        elements.append(table)
    else:
        elements.append(Paragraph("Aucun colis trouvé dans ce lot.", styles['Normal']))
    
    # Pied de page
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(
        f"Généré le {timezone.now().strftime('%d/%m/%Y à %H:%M')}", 
        styles['Italic']
    ))
    
    # Générer le PDF
    doc.build(elements)
    
    return response
