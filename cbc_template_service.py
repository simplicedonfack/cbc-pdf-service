"""
CBC_TEMPLATE.PY — Modèle officiel Commercial Bank Cameroun
Réutilisable pour tous les rapports DMSAV.

Usage :
    from cbc_template import CBCTemplate
    
    tmpl = CBCTemplate()
    tmpl.build(
        output_path='/home/claude/mon_rapport.pdf',
        content_flowables=[...],   # liste de Paragraph, Table, Spacer...
        titre='MON RAPPORT',
        sous_titre='Sous-titre',
        reference='REF-20260612',
    )
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from datetime import date
import os

# ── Couleurs officielles CBC ───────────────────────────────────
CBC_OR    = colors.HexColor('#DEA900')   # Couleur cadre & accents
CBC_GRIS  = colors.HexColor('#44546A')   # Couleur titres & en-tête
CBC_BLEU  = colors.HexColor('#4472C4')   # Tableaux secondaires
CBC_VERT  = colors.HexColor('#70AD47')   # Statuts positifs
CBC_ROUGE = colors.HexColor('#C00000')   # Statuts négatifs / alertes
CBC_ORANG = colors.HexColor('#ED7D31')   # Statuts intermédiaires
CBC_GRIS_L= colors.HexColor('#E7E6E6')   # Fond lignes alternées
BLANC     = colors.white

# ── Chemin du logo (à adapter si déplacé) ─────────────────────
LOGO_PATH = os.path.join(os.path.dirname(__file__), 'logo-cbc.jpeg')

def cbc_style(name, font='Helvetica', size=9, color='#000000', **kw):
    """Créer un ParagraphStyle aux couleurs CBC."""
    return ParagraphStyle(name, fontName=font, fontSize=size,
                          textColor=colors.HexColor(color), **kw)

# Styles prêts à l'emploi
S_TITRE    = cbc_style('CBC_T1','Helvetica-Bold',14,'#44546A',alignment=TA_CENTER,spaceAfter=3)
S_SOUS     = cbc_style('CBC_T2','Helvetica',     10,'#44546A',alignment=TA_CENTER,spaceAfter=2)
S_REF      = cbc_style('CBC_RF','Helvetica-Bold', 9,'#44546A',alignment=TA_RIGHT, spaceAfter=2)
S_H1       = cbc_style('CBC_H1','Helvetica-Bold',11,'#44546A',spaceBefore=8,spaceAfter=4)
S_H2       = cbc_style('CBC_H2','Helvetica-Bold', 9,'#4472C4',spaceBefore=5,spaceAfter=3)
S_BODY     = cbc_style('CBC_BB','Helvetica',       9,'#333333',spaceAfter=3)
S_SMALL    = cbc_style('CBC_SM','Helvetica',       8,'#888888',spaceAfter=2)
S_FOOTER   = cbc_style('CBC_FT','Helvetica',       7,'#888888',alignment=TA_CENTER)

# Style pour le contenu des cellules de tableau avec retour à la ligne automatique
S_CELL     = cbc_style('CBC_CELL','Helvetica',     8,'#333333', leading=10)


def cbc_table(data, widths, hdr_bg=None, wrap_cols=None):
    """
    Tableau aux couleurs CBC avec en-tête gris et lignes alternées.

    wrap_cols : liste optionnelle d'indices de colonnes (0-based) dont le
    contenu doit être enveloppé dans un Paragraph pour permettre le retour
    à la ligne automatique. Sans cela, un texte plus long que la largeur
    de colonne déborde et chevauche les colonnes voisines (PDF portrait).

    Les colonnes hors wrap_cols restent en texte brut — utile pour les
    colonnes courtes (statuts, taux, #) qui reçoivent souvent une
    coloration conditionnelle via TableStyle TEXTCOLOR après création.
    """
    wrap_cols = set(wrap_cols or [])

    if wrap_cols:
        new_data = []
        for r_idx, row in enumerate(data):
            new_row = []
            for c_idx, cell in enumerate(row):
                if r_idx > 0 and c_idx in wrap_cols:
                    texte = '' if cell is None else str(cell)
                    new_row.append(Paragraph(texte, S_CELL))
                else:
                    new_row.append(cell)
            new_data.append(new_row)
        data = new_data

    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ('FONTNAME',      (0,0),(-1,0),  'Helvetica-Bold'),
        ('FONTSIZE',      (0,0),(-1,-1), 8),
        ('BACKGROUND',    (0,0),(-1,0),  hdr_bg or CBC_GRIS),
        ('TEXTCOLOR',     (0,0),(-1,0),  BLANC),
        ('GRID',          (0,0),(-1,-1), 0.3, colors.HexColor('#CCCCCC')),
        ('PADDING',       (0,0),(-1,-1), 4),
        ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
        ('ROWBACKGROUNDS',(0,1),(-1,-1), [BLANC, CBC_GRIS_L]),
    ]))
    return t

def _draw_round2diag_rect(canvas, x, y, w, h, radius):
    """
    Cadre CBC officiel : round2DiagRect
    Coins arrondis sur la diagonale haut-droit / bas-gauche.
    Coins droits sur haut-gauche / bas-droit.
    Rayon = 18.4mm sur A4 standard.
    """
    r = radius
    canvas.setStrokeColor(CBC_OR)
    canvas.setLineWidth(1.5)
    p = canvas.beginPath()
    # Partir du coin haut-gauche (droit)
    p.moveTo(x, y + h)
    # Aller vers haut-droit avec arrondi (quart cercle)
    p.lineTo(x + w - r, y + h)
    p.arcTo(x + w - 2*r, y + h - 2*r, x + w, y + h,
            startAng=90, extent=-90)
    # Descendre vers bas-droit (droit)
    p.lineTo(x + w, y)
    # Aller vers bas-gauche avec arrondi (quart cercle)
    p.lineTo(x + r, y)
    p.arcTo(x, y, x + 2*r, y + 2*r,
            startAng=270, extent=-90)
    # Remonter vers haut-gauche (droit)
    p.lineTo(x, y + h)
    p.close()
    canvas.drawPath(p, stroke=1, fill=0)

def _draw_page(canvas, doc, ref, date_str):
    """Dessine le cadre, le logo et le pied sur chaque page."""
    canvas.saveState()
    pw, ph = A4
    margin = 7*mm

    # Cadre doré round2DiagRect
    _draw_round2diag_rect(canvas, margin, margin,
                          pw - 2*margin, ph - 2*margin,
                          radius=18.4*mm)

    # Logo CBC centré en haut
    if os.path.exists(LOGO_PATH):
        lw, lh = 45*mm, 18*mm
        logo_y = ph - margin - lh - 3*mm
        canvas.drawImage(LOGO_PATH,
                        (pw - lw) / 2, logo_y,
                        width=lw, height=lh,
                        preserveAspectRatio=True, mask='auto')

    # Textes direction collés sous le logo
    canvas.setFillColor(CBC_GRIS)
    canvas.setFont('Helvetica-Bold', 9)
    canvas.drawCentredString(pw/2, ph - margin - 25*mm,
                             "Direction Centrale de l'Exploitation et du Reseau")
    canvas.setFont('Helvetica', 8)
    canvas.drawCentredString(pw/2, ph - margin - 30*mm,
                             "Direction du Marketing et Service Apres-Vente")

    # Pied de page
    canvas.setStrokeColor(CBC_OR)
    canvas.setLineWidth(0.5)
    canvas.line(margin + 5*mm, margin + 10*mm,
                pw - margin - 5*mm, margin + 10*mm)
    canvas.setFillColor(CBC_GRIS)
    canvas.setFont('Helvetica', 7)
    canvas.drawString(margin + 8*mm, margin + 5*mm, f'Ref : {ref}')
    canvas.drawCentredString(pw/2, margin + 5*mm, f'{date_str} — Confidentiel')
    canvas.drawRightString(pw - margin - 8*mm, margin + 5*mm, f'Page {doc.page}')

    canvas.restoreState()


class CBCTemplate:
    """
    Classe principale du modèle CBC.
    
    Exemple d'utilisation :
        tmpl = CBCTemplate()
        st = []
        st.append(Paragraph("Section 1", tmpl.S_H1))
        st.append(tmpl.table([['Col1','Col2'],['Val1','Val2']], [80*mm, 80*mm]))
        tmpl.build('/home/claude/rapport.pdf', st, 
                   titre='MON RAPPORT',
                   sous_titre='Description',
                   reference='REF-001')
    """

    S_TITRE = S_TITRE
    S_SOUS  = S_SOUS
    S_REF   = S_REF
    S_H1    = S_H1
    S_H2    = S_H2
    S_BODY  = S_BODY
    S_SMALL = S_SMALL
    S_CELL  = S_CELL

    OR    = CBC_OR
    GRIS  = CBC_GRIS
    BLEU  = CBC_BLEU
    VERT  = CBC_VERT
    ROUGE = CBC_ROUGE
    ORANG = CBC_ORANG

    def table(self, data, widths, hdr_bg=None, wrap_cols=None):
        return cbc_table(data, widths, hdr_bg, wrap_cols)

    def spacer(self, h_mm=4):
        return Spacer(1, h_mm*mm)

    def separateur(self):
        return HRFlowable(width='100%', thickness=0.5, color=CBC_GRIS_L)

    def build(self, output_path_or_buf, flowables, titre, sous_titre='', reference='', statut=''):
        today    = date.today()
        date_str = today.strftime('%d/%m/%Y')
        ref      = reference or f"DMSAV-{today.strftime('%Y%m%d')}"

        doc = SimpleDocTemplate(
            output_path_or_buf, pagesize=A4,
            leftMargin=18*mm, rightMargin=18*mm,
            topMargin=55*mm, bottomMargin=22*mm,
        )

        # En-tête du document
        header = []
        header.append(Paragraph(titre, S_TITRE))
        if sous_titre:
            header.append(Paragraph(sous_titre, S_SOUS))
        header.append(Paragraph(f'Ref : {ref}', S_REF))
        header.append(HRFlowable(width='100%', thickness=0.5, color=CBC_GRIS_L))
        header.append(Spacer(1, 4*mm))

        def _on_page(canvas, doc):
            _draw_page(canvas, doc, ref, date_str)

        doc.build(header + flowables,
                  onFirstPage=_on_page,
                  onLaterPages=_on_page)
        if isinstance(output_path_or_buf, str):
            print(f'Rapport genere : {output_path_or_buf}')
        return output_path_or_buf


# ── Test rapide ───────────────────────────────────────────────
if __name__ == '__main__':
    tmpl = CBCTemplate()
    st = []
    st.append(Paragraph('1.   TEST DU MODELE', S_H1))
    st.append(Paragraph('Ce document teste le modele CBC.', S_BODY))
    st.append(Spacer(1, 5*mm))
    st.append(cbc_table(
        [['Colonne 1','Colonne 2','Colonne 3'],
         ['Valeur A', 'Valeur B', 'Valeur C'],
         ['Valeur D', 'Valeur E', 'Valeur F']],
        [60*mm, 60*mm, 54*mm]
    ))
    tmpl.build('/home/claude/test_modele_CBC.pdf', st,
               titre='TEST MODELE CBC',
               sous_titre='Verification de la trame officielle',
               reference='TEST-001')


def build_to_buffer(buf, flowables, titre, sous_titre='', reference='', statut=''):
    """Version buffer de CBCTemplate.build() pour le microservice."""
    tmpl = CBCTemplate()
    today = date.today()
    date_str = today.strftime('%d/%m/%Y')
    ref = reference or f"DMSAV-{today.strftime('%Y%m%d')}"

    from reportlab.platypus import SimpleDocTemplate
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, Spacer
    from reportlab.platypus import HRFlowable

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=55*mm, bottomMargin=22*mm,
    )

    header = []
    header.append(Paragraph(titre, S_TITRE))
    if sous_titre:
        header.append(Paragraph(sous_titre, S_SOUS))
    header.append(Paragraph(f'Ref : {ref}', S_REF))
    header.append(HRFlowable(width='100%', thickness=0.5, color=CBC_GRIS_L))
    header.append(Spacer(1, 4*mm))

    def _on_page(canvas, doc):
        _draw_page(canvas, doc, ref, date_str)

    doc.build(header + flowables, onFirstPage=_on_page, onLaterPages=_on_page)
