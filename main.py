"""
CBC PDF Microservice
Service FastAPI qui génère des rapports PDF avec la trame officielle CBC.
Déployable sur Render.com (free tier).
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
import io
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from cbc_template_service import CBCTemplate, cbc_table, S_H1, S_BODY, S_SMALL
from cbc_template_service import CBC_GRIS, CBC_OR, CBC_BLEU, CBC_VERT, CBC_ROUGE, CBC_ORANG, BLANC
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, HRFlowable
from datetime import date

app = FastAPI(title="CBC PDF Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://dmsav.vercel.app", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Couleur additionnelle pour le statut "Repos" (indigo)
CBC_INDIGO = colors.HexColor('#6366F1')

# ── Modèles de données ─────────────────────────────────────────

class CollaborateurPresence(BaseModel):
    nom: str
    prenom: str
    role: str
    statut: str
    heure_arrivee: Optional[str] = None
    commentaire: Optional[str] = None
    source: Optional[str] = "manuel"

class EvolutionJour(BaseModel):
    date: str
    taux: int
    presents: int
    total: int

class RapportPresenceRequest(BaseModel):
    date: str
    type_jour: str
    statut_fiche: str
    collaborateurs: List[CollaborateurPresence]
    evolution: Optional[List[EvolutionJour]] = []

class ActionPlan(BaseModel):
    numero: Optional[int] = None
    intitule: str
    categorie: str
    axe_strategique: Optional[str] = None
    statut: str
    taux_realisation: int
    responsables_texte: Optional[str] = None
    commentaire_realisation: Optional[str] = None
    contrainte_bloquante: bool = False

class AjustementPlan(BaseModel):
    action_intitule: str
    type_ajustement: str
    motif: str
    date_ajustement: str

class RapportPlanRequest(BaseModel):
    annee: int
    titre: str
    version: str
    budget_prevu: float
    taux_realisation_global: int
    actions: List[ActionPlan]
    ajustements: Optional[List[AjustementPlan]] = []

# ── Modèles — Rapport Superviseur ─────────────────────────────

class TacheRetard(BaseModel):
    titre: str
    collaborateur: str
    retard: str

class CracSoumisItem(BaseModel):
    collaborateur: str
    date_soumission: str

class StatTaches(BaseModel):
    en_attente: int
    en_cours: int
    soumise: int
    validee: int
    rejetee: int

class StatPlan(BaseModel):
    annee: int
    taux_moyen: int
    total: int
    realisees: int
    en_cours: int
    a_risque: int
    contraintes: int

class ActionBloquante(BaseModel):
    intitule: str
    responsables: Optional[str] = None

class ActionRisque(BaseModel):
    intitule: str
    statut: str

class StatObjectifs(BaseModel):
    total: int
    atteints: int
    en_cours: int
    non_atteints: int
    partiellement: int

class StatBudget(BaseModel):
    total_prevu: float
    total_realise: float

class RapportSuperviseurRequest(BaseModel):
    date: str
    nb_utilisateurs: int
    stat_taches: StatTaches
    taches_en_retard: List[TacheRetard] = []
    crac_soumis: List[CracSoumisItem] = []
    presence: Optional[RapportPresenceRequest] = None
    stat_plan: Optional[StatPlan] = None
    actions_bloquantes: List[ActionBloquante] = []
    actions_risque: List[ActionRisque] = []
    stat_objectifs: StatObjectifs
    stat_budget: StatBudget

# ── Modèles — Product Management ──────────────────────────────

class KpisProduit(BaseModel):
    pnb_realise: Optional[float] = None
    pnb_objectif: Optional[float] = None
    ventes_nettes: Optional[int] = None
    commissions_cumul: Optional[float] = None
    nb_clients_actifs: Optional[int] = None
    taux_actifs: Optional[float] = None
    taux_inactifs: Optional[float] = None
    taux_activation_30j: Optional[float] = None
    taux_retention: Optional[float] = None
    cross_sell_ratio: Optional[float] = None
    respect_sla: Optional[float] = None
    nb_anomalies: Optional[int] = None
    taux_litiges: Optional[float] = None
    conformite_produit: Optional[str] = None
    nb_actions_en_cours: Optional[int] = None
    taux_avancement_global: Optional[float] = None

class ActionPM(BaseModel):
    titre: str
    type: Optional[str] = None
    statut: Optional[str] = None
    priorite: Optional[str] = None
    date_echeance: Optional[str] = None
    responsable: Optional[str] = None

class ProduitInfo(BaseModel):
    code: Optional[str] = None
    libelle: Optional[str] = None
    statut: Optional[str] = None
    description: Optional[str] = None
    gamme: Optional[str] = None
    date_lancement: Optional[str] = None

class ChefProduit(BaseModel):
    nom: Optional[str] = None
    prenom: Optional[str] = None

class RapportProduitRequest(BaseModel):
    type: str = "fiche_produit"
    periode: str
    periode_label: str
    produit: ProduitInfo
    chefs_produit: List[ChefProduit] = []
    kpis: Optional[KpisProduit] = None
    actions_en_cours: List[ActionPM] = []
    genere_par: str
    genere_le: str

# ── Modèles — Rapport Portefeuille PM ─────────────────────────

class ProduitSynthese(BaseModel):
    code: Optional[str] = None
    libelle: Optional[str] = None
    statut: Optional[str] = None
    gamme: Optional[str] = None
    pnb_realise: Optional[float] = None
    pnb_objectif: Optional[float] = None
    nb_clients_actifs: Optional[int] = None
    taux_retention: Optional[float] = None
    respect_sla: Optional[float] = None
    nb_actions_en_cours: int = 0
    nb_actions_en_retard: int = 0

class MembreSynthese(BaseModel):
    nom: Optional[str] = None
    prenom: Optional[str] = None
    role_fonctionnel: Optional[str] = None
    nb_produits: int = 0
    produits: List[ProduitSynthese] = []

class SyntheseGlobale(BaseModel):
    nb_membres: int
    nb_produits: int
    nb_actions_en_cours: int
    nb_actions_en_retard: int

class RapportPortefeuillePMRequest(BaseModel):
    type: str = "rapport_portefeuille"
    periode: str
    periode_label: str
    synthese: SyntheseGlobale
    membres: List[MembreSynthese] = []
    genere_par: str
    genere_le: str

# ── Helpers ─────────────────────────────────────────────────────

STATUT_FR = {
    'present': 'Present', 'absent': 'Absent', 'conge': 'Conge',
    'retard': 'Retard', 'maladie': 'Maladie', 'permission': 'Permission',
    'mission': 'Mission', 'repos': 'Repos', 'ferie': 'Ferie',
}
STATUT_COLOR = {
    'present': CBC_VERT, 'absent': CBC_ROUGE, 'conge': CBC_ORANG,
    'retard': CBC_ORANG, 'maladie': CBC_ROUGE, 'permission': CBC_BLEU,
    'mission': CBC_BLEU, 'repos': CBC_INDIGO,
}
JOURS_ABBR_FR = ['Lun','Mar','Mer','Jeu','Ven','Sam','Dim']
MOIS_ABBR_FR  = ['Janv','Fevr','Mars','Avr','Mai','Juin','Juil','Aout','Sept','Oct','Nov','Dec']

def _formater_date_courte(iso_date: str) -> str:
    try:
        d = date.fromisoformat(iso_date)
        return f"{JOURS_ABBR_FR[d.weekday()]}. {d.day:02d} {MOIS_ABBR_FR[d.month-1]}"
    except Exception:
        return iso_date

def _formater_fcfa(montant: float) -> str:
    return f"{montant:,.0f}".replace(',', ' ') + " FCFA"

def _formater_millions(montant: Optional[float]) -> str:
    if montant is None:
        return '—'
    if montant >= 1_000_000:
        return f"{montant/1_000_000:.1f} M"
    if montant >= 1_000:
        return f"{montant/1_000:.0f} K"
    return f"{montant:,.0f}"

def _pct_str(val: Optional[float]) -> str:
    return f"{val:.1f}%" if val is not None else '—'

def _int_str(val: Optional[int]) -> str:
    return str(val) if val is not None else '—'

TYPE_JOUR_FR = {
    'ouvre': 'Jour ouvre', 'ouvrable': 'Jour ouvrable',
    'repos': 'Repos hebdomadaire', 'ferie': 'Jour ferie',
}
CATEGORIE_FR = {
    'personnes': 'Personnes',
    'promotion_communication': 'Promotion & Communication',
    'distribution': 'Distribution',
    'experience_client': 'Experience Client',
    'evenements': 'Evenements',
    'numerique': 'Numerique',
    'autre': 'Autre',
}
STATUT_PLAN_FR = {
    'planifiee': 'Planifiee', 'en_cours': 'En cours',
    'realisee_totale': 'Realisee', 'realisee_partielle': 'Part. realisee',
    'retardee': 'Retardee', 'reportee': 'Reportee',
    'suspendue': 'Suspendue', 'annulee': 'Annulee',
}
STATUT_PRODUIT_FR = {
    'actif': 'Actif', 'en_lancement': 'En lancement',
    'en_developpement': 'En developpement', 'en_declin': 'En declin', 'retire': 'Retire',
}
STATUT_PRODUIT_COLOR = {
    'actif': CBC_VERT, 'en_lancement': CBC_ORANG,
    'en_developpement': CBC_BLEU, 'en_declin': CBC_INDIGO, 'retire': CBC_GRIS,
}
PRIORITE_FR = {
    'haute': 'Haute', 'moyenne': 'Moyenne', 'basse': 'Basse',
}
PRIORITE_COLOR = {
    'haute': CBC_ROUGE, 'moyenne': CBC_ORANG, 'basse': CBC_GRIS,
}
TYPE_ACTION_FR = {
    'tache': 'Tache', 'jalon': 'Jalon', 'incident': 'Incident', 'comite': 'Comite',
}
CONFORMITE_FR = {
    'conforme': 'Conforme', 'en_cours': 'En cours', 'non_conforme': 'Non conforme',
}
CONFORMITE_COLOR = {
    'conforme': CBC_VERT, 'en_cours': CBC_ORANG, 'non_conforme': CBC_ROUGE,
}
ROLE_FM_FR = {
    'directeur_produit': 'Directeur Produit',
    'chef_produit': 'Chef de Produit',
    'observateur': 'Observateur',
}

# ── Routes ───────────────────────────────────────────────────────

@app.get("/")
def health():
    return {"status": "ok", "service": "CBC PDF Service", "version": "1.0.0"}

@app.post("/rapport/presence")
def generer_rapport_presence(req: RapportPresenceRequest):
    """Génère un rapport PDF de présence avec la trame CBC officielle."""
    try:
        buf = io.BytesIO()
        tmpl = CBCTemplate()

        total      = len(req.collaborateurs)
        presents   = sum(1 for c in req.collaborateurs if c.statut == 'present')
        en_repos   = sum(1 for c in req.collaborateurs if c.statut == 'repos')
        en_mission = sum(1 for c in req.collaborateurs if c.statut == 'mission')
        conges     = sum(1 for c in req.collaborateurs if c.statut in ('conge', 'maladie', 'permission'))
        absents    = sum(1 for c in req.collaborateurs if c.statut == 'absent')
        retards    = sum(1 for c in req.collaborateurs if c.statut == 'retard')

        denom = total - en_repos
        taux  = round(presents / denom * 100) if denom > 0 else None

        try:
            d = date.fromisoformat(req.date)
            jours_fr = ['Lundi','Mardi','Mercredi','Jeudi','Vendredi','Samedi','Dimanche']
            date_str = f"{jours_fr[d.weekday()]} {d.strftime('%d/%m/%Y')}"
        except:
            date_str = req.date

        nature_str = TYPE_JOUR_FR.get(req.type_jour, req.type_jour.replace('_', ' ').capitalize())
        ref = f"DMSAV-PRES-{req.date.replace('-','')}"
        st = []

        st.append(Paragraph('1.   SYNTHESE DU JOUR', S_H1))
        st.append(Paragraph(f'Nature du jour : <b>{nature_str}</b>', S_BODY))
        st.append(Spacer(1, 2*mm))

        taux_str = f'{taux}%' if taux is not None else '—'
        taux_col = CBC_GRIS if taux is None else (CBC_VERT if taux >= 80 else (CBC_ORANG if taux >= 60 else CBC_ROUGE))

        kt = Table(
            [['Presents','En repos','En mission','Conges','Absents','Retards','Total','TAUX'],
             [str(presents), str(en_repos), str(en_mission), str(conges),
              str(absents), str(retards), str(total), taux_str]],
            colWidths=[22*mm]*7+[24*mm], rowHeights=[10*mm, 16*mm])
        kt.setStyle(TableStyle([
            ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
            ('FONTNAME',(0,1),(-1,1),'Helvetica-Bold'),
            ('FONTSIZE',(0,0),(-1,0),7.5), ('FONTSIZE',(0,1),(-1,1),15),
            ('BACKGROUND',(0,0),(-1,0),CBC_GRIS), ('TEXTCOLOR',(0,0),(-1,0),BLANC),
            ('BACKGROUND',(0,1),(6,1),colors.HexColor('#F5F6FA')),
            ('BACKGROUND',(7,1),(7,1),CBC_GRIS),
            ('TEXTCOLOR',(0,1),(0,1),CBC_VERT),
            ('TEXTCOLOR',(1,1),(1,1),CBC_INDIGO),
            ('TEXTCOLOR',(2,1),(2,1),CBC_BLEU),
            ('TEXTCOLOR',(3,1),(3,1),CBC_ORANG),
            ('TEXTCOLOR',(4,1),(4,1),CBC_ROUGE),
            ('TEXTCOLOR',(5,1),(5,1),CBC_ORANG),
            ('TEXTCOLOR',(6,1),(6,1),CBC_GRIS),
            ('TEXTCOLOR',(7,1),(7,1),taux_col),
            ('ALIGN',(0,0),(-1,-1),'CENTER'), ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
            ('GRID',(0,0),(-1,-1),0.3,colors.HexColor('#CCCCCC')),
        ]))
        st += [kt, Spacer(1,5*mm)]

        st.append(Paragraph('2.   DETAIL PAR COLLABORATEUR', S_H1))
        d_data = [['#','Nom et Prenom','Fonction','Statut','Heure','Observations']]
        for i, c in enumerate(req.collaborateurs, 1):
            d_data.append([str(i), f'{c.nom} {c.prenom}', c.role,
                           STATUT_FR.get(c.statut, c.statut),
                           c.heure_arrivee or '—', c.commentaire or ''])
        dt = cbc_table(d_data, [8*mm,50*mm,24*mm,22*mm,18*mm,52*mm], wrap_cols=[1,5])
        for i, c in enumerate(req.collaborateurs, 1):
            col = STATUT_COLOR.get(c.statut, CBC_GRIS)
            dt.setStyle(TableStyle([
                ('TEXTCOLOR',(3,i),(3,i),col),
                ('FONTNAME',(3,i),(3,i),'Helvetica-Bold')
            ]))
        st += [dt, Spacer(1,5*mm)]

        if req.evolution:
            st.append(Paragraph('3.   EVOLUTION DE LA PRESENCE — 7 JOURS (HORS REPOS)', S_H1))
            e_data = [['Date','Presents','Total (hors repos)','Taux']]
            for e in req.evolution:
                e_data.append([e.date, str(e.presents), str(e.total), f'{e.taux}%'])
            et = cbc_table(e_data, [40*mm, 30*mm, 40*mm, 30*mm])
            st += [et, Spacer(1,5*mm)]

        tmpl.build(buf, st,
                   titre='RAPPORT DE PRESENCE',
                   sous_titre=f'{date_str} — Direction Marketing & SAV',
                   reference=ref,
                   statut=req.statut_fiche)

        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type='application/pdf',
            headers={'Content-Disposition': f'attachment; filename="Rapport_Presence_{req.date}.pdf"'}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/rapport/plan-marketing")
def generer_rapport_plan(req: RapportPlanRequest):
    """Génère un rapport PDF du Plan Marketing avec la trame CBC officielle."""
    try:
        buf = io.BytesIO()
        tmpl = CBCTemplate()

        total = len(req.actions)
        realisees  = sum(1 for a in req.actions if a.statut in ('realisee_totale','realisee_partielle'))
        en_cours   = sum(1 for a in req.actions if a.statut == 'en_cours')
        a_risque   = sum(1 for a in req.actions if a.statut in ('retardee','reportee','suspendue'))
        contraintes= sum(1 for a in req.actions if a.contrainte_bloquante)
        taux_moyen = round(sum(a.taux_realisation for a in req.actions)/total) if total > 0 else 0
        ref = f"DMSAV-PLAN-{req.annee}"
        st = []

        st.append(Paragraph('1.   SYNTHESE GLOBALE', S_H1))
        k_data = [
            ['Indicateur','Valeur','Commentaire'],
            ['Taux moyen de realisation', f'{taux_moyen}%', 'Moyenne des taux individuels'],
            ['Actions en cours', str(en_cours), f'sur {total} actions'],
            ['Actions realisees', str(realisees), f'{round(realisees/total*100) if total else 0}% du plan'],
            ['Actions a risque', str(a_risque), 'Retardees, reportees ou suspendues'],
            ['Contraintes bloquantes', str(contraintes), 'Necessitent une decision'],
            ['Budget prevu', f"{req.budget_prevu/1e6:.0f} M FCFA", f'Exercice {req.annee}'],
        ]
        kt = cbc_table(k_data, [80*mm, 30*mm, 64*mm], wrap_cols=[0,2])
        taux_col = CBC_VERT if taux_moyen>=50 else CBC_ROUGE
        kt.setStyle(TableStyle([
            ('FONTNAME',(0,-1),(-1,-1),'Helvetica-Bold'),
            ('BACKGROUND',(0,-1),(-1,-1),colors.HexColor('#EAF0F8')),
            ('TEXTCOLOR',(1,1),(2,1),taux_col),
        ]))
        st += [kt, Spacer(1,5*mm)]

        st.append(Paragraph('2.   PLAN D\'ACTIONS — ETAT DETAILLE', S_H1))
        d_data = [['#','Intitule','Categorie','Statut','Taux','Contrainte']]
        for a in req.actions:
            d_data.append([
                str(a.numero or ''),
                (a.intitule or '')[:120],
                CATEGORIE_FR.get(a.categorie, a.categorie),
                STATUT_PLAN_FR.get(a.statut, a.statut),
                f'{a.taux_realisation}%',
                'OUI' if a.contrainte_bloquante else '',
            ])
        dt = cbc_table(d_data, [8*mm, 60*mm, 28*mm, 22*mm, 12*mm, 16*mm], wrap_cols=[1,2])
        for i, a in enumerate(req.actions, 1):
            if a.contrainte_bloquante:
                dt.setStyle(TableStyle([('TEXTCOLOR',(5,i),(5,i),CBC_ROUGE),('FONTNAME',(5,i),(5,i),'Helvetica-Bold')]))
            c = CBC_VERT if a.statut in ('realisee_totale',) else (CBC_ROUGE if a.statut in ('retardee','suspendue','annulee') else CBC_GRIS)
            dt.setStyle(TableStyle([('TEXTCOLOR',(3,i),(3,i),c)]))
        st += [dt, Spacer(1,5*mm)]

        if req.ajustements:
            st.append(Paragraph('3.   MATRICE DES AJUSTEMENTS', S_H1))
            aj_data = [['Action concernee','Type','Motif','Date']]
            for aj in req.ajustements:
                aj_data.append([
                    (aj.action_intitule or '')[:120],
                    aj.type_ajustement,
                    (aj.motif or '')[:200],
                    aj.date_ajustement,
                ])
            st += [cbc_table(aj_data, [50*mm, 20*mm, 70*mm, 20*mm], wrap_cols=[0,2]), Spacer(1,5*mm)]

        tmpl.build(buf, st,
                   titre=f'RAPPORT PLAN MARKETING {req.annee}',
                   sous_titre=f'Version {req.version} — Budget {req.budget_prevu/1e6:.0f} M FCFA',
                   reference=ref)

        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type='application/pdf',
            headers={'Content-Disposition': f'attachment; filename="Rapport_Plan_Marketing_{req.annee}.pdf"'}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _section_presence(req: RapportPresenceRequest, numero: int) -> list:
    st = []
    total      = len(req.collaborateurs)
    presents   = sum(1 for c in req.collaborateurs if c.statut == 'present')
    en_repos   = sum(1 for c in req.collaborateurs if c.statut == 'repos')
    en_mission = sum(1 for c in req.collaborateurs if c.statut == 'mission')
    conges     = sum(1 for c in req.collaborateurs if c.statut in ('conge', 'maladie', 'permission'))
    absents    = sum(1 for c in req.collaborateurs if c.statut == 'absent')
    retards    = sum(1 for c in req.collaborateurs if c.statut == 'retard')
    denom = total - en_repos
    taux  = round(presents / denom * 100) if denom > 0 else None
    nature_str = TYPE_JOUR_FR.get(req.type_jour, req.type_jour.replace('_', ' ').capitalize())

    st.append(Paragraph(f'{numero}.   PRESENCE DU JOUR', S_H1))
    st.append(Paragraph(f'Nature du jour : <b>{nature_str}</b>', S_BODY))
    st.append(Spacer(1, 2*mm))

    taux_str = f'{taux}%' if taux is not None else '—'
    taux_col = CBC_GRIS if taux is None else (CBC_VERT if taux >= 80 else (CBC_ORANG if taux >= 60 else CBC_ROUGE))

    kt = Table(
        [['Presents','En repos','En mission','Conges','Absents','Retards','Total','TAUX'],
         [str(presents), str(en_repos), str(en_mission), str(conges),
          str(absents), str(retards), str(total), taux_str]],
        colWidths=[22*mm]*7+[24*mm], rowHeights=[10*mm, 16*mm])
    kt.setStyle(TableStyle([
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('FONTNAME',(0,1),(-1,1),'Helvetica-Bold'),
        ('FONTSIZE',(0,0),(-1,0),7.5), ('FONTSIZE',(0,1),(-1,1),15),
        ('BACKGROUND',(0,0),(-1,0),CBC_GRIS), ('TEXTCOLOR',(0,0),(-1,0),BLANC),
        ('BACKGROUND',(0,1),(6,1),colors.HexColor('#F5F6FA')),
        ('BACKGROUND',(7,1),(7,1),CBC_GRIS),
        ('TEXTCOLOR',(0,1),(0,1),CBC_VERT), ('TEXTCOLOR',(1,1),(1,1),CBC_INDIGO),
        ('TEXTCOLOR',(2,1),(2,1),CBC_BLEU), ('TEXTCOLOR',(3,1),(3,1),CBC_ORANG),
        ('TEXTCOLOR',(4,1),(4,1),CBC_ROUGE), ('TEXTCOLOR',(5,1),(5,1),CBC_ORANG),
        ('TEXTCOLOR',(6,1),(6,1),CBC_GRIS), ('TEXTCOLOR',(7,1),(7,1),taux_col),
        ('ALIGN',(0,0),(-1,-1),'CENTER'), ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('GRID',(0,0),(-1,-1),0.3,colors.HexColor('#CCCCCC')),
    ]))
    st += [kt, Spacer(1,5*mm)]

    st.append(Paragraph('Detail par collaborateur', S_BODY))
    d_data = [['#','Nom et Prenom','Fonction','Statut','Heure','Observations']]
    for i, c in enumerate(req.collaborateurs, 1):
        d_data.append([str(i), f'{c.nom} {c.prenom}', c.role,
                       STATUT_FR.get(c.statut, c.statut),
                       c.heure_arrivee or '—', c.commentaire or ''])
    dt = cbc_table(d_data, [8*mm,50*mm,24*mm,22*mm,18*mm,52*mm], wrap_cols=[1,5])
    for i, c in enumerate(req.collaborateurs, 1):
        col = STATUT_COLOR.get(c.statut, CBC_GRIS)
        dt.setStyle(TableStyle([
            ('TEXTCOLOR',(3,i),(3,i),col),
            ('FONTNAME',(3,i),(3,i),'Helvetica-Bold')
        ]))
    st += [dt, Spacer(1,5*mm)]

    if req.evolution:
        st.append(Paragraph('Evolution de la presence - 7 jours (hors repos)', S_BODY))
        e_data = [['Date','Presents','Total (hors repos)','Taux']]
        for e in req.evolution:
            e_data.append([_formater_date_courte(e.date), str(e.presents), str(e.total), f'{e.taux}%'])
        et = cbc_table(e_data, [40*mm, 30*mm, 40*mm, 30*mm])
        st += [et, Spacer(1,5*mm)]

    return st


@app.post("/rapport/superviseur")
def generer_rapport_superviseur(req: RapportSuperviseurRequest):
    try:
        buf = io.BytesIO()
        tmpl = CBCTemplate()

        try:
            d = date.fromisoformat(req.date)
            jours_fr = ['Lundi','Mardi','Mercredi','Jeudi','Vendredi','Samedi','Dimanche']
            date_str = f"{jours_fr[d.weekday()]} {d.strftime('%d/%m/%Y')}"
        except:
            date_str = req.date

        ref = f"DMSAV-SUPV-{req.date.replace('-','')}"
        st = []

        st.append(Paragraph('1.   INDICATEURS CLES DU JOUR', S_H1))
        nb_retard = len(req.taches_en_retard)
        nb_crac   = len(req.crac_soumis)

        kt = Table(
            [['Taches en retard','CRAC a valider','Taches en cours','Collaborateurs'],
             [str(nb_retard), str(nb_crac), str(req.stat_taches.en_cours), str(req.nb_utilisateurs)]],
            colWidths=[42*mm]*4, rowHeights=[10*mm, 16*mm])
        kt.setStyle(TableStyle([
            ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
            ('FONTNAME',(0,1),(-1,1),'Helvetica-Bold'),
            ('FONTSIZE',(0,0),(-1,0),8), ('FONTSIZE',(0,1),(-1,1),18),
            ('BACKGROUND',(0,0),(-1,0),CBC_GRIS), ('TEXTCOLOR',(0,0),(-1,0),BLANC),
            ('BACKGROUND',(0,1),(-1,1),colors.HexColor('#F5F6FA')),
            ('TEXTCOLOR',(0,1),(0,1), CBC_ROUGE if nb_retard > 0 else CBC_VERT),
            ('TEXTCOLOR',(1,1),(1,1), CBC_BLEU if nb_crac > 0 else CBC_VERT),
            ('TEXTCOLOR',(2,1),(2,1), CBC_BLEU),
            ('TEXTCOLOR',(3,1),(3,1), CBC_GRIS),
            ('ALIGN',(0,0),(-1,-1),'CENTER'), ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
            ('GRID',(0,0),(-1,-1),0.3,colors.HexColor('#CCCCCC')),
        ]))
        st += [kt, Spacer(1,5*mm)]

        st.append(Paragraph('Taches en retard', S_BODY))
        if not req.taches_en_retard:
            st.append(Paragraph('Aucun retard - bonne gestion.', S_SMALL))
        else:
            t_data = [['Collaborateur','Tache','Retard']]
            for t in req.taches_en_retard:
                t_data.append([t.collaborateur, (t.titre or '')[:70], t.retard])
            tt = cbc_table(t_data, [50*mm, 90*mm, 30*mm], wrap_cols=[1])
            for i, t in enumerate(req.taches_en_retard, 1):
                tt.setStyle(TableStyle([
                    ('TEXTCOLOR',(2,i),(2,i), CBC_ROUGE),
                    ('FONTNAME',(2,i),(2,i),'Helvetica-Bold'),
                ]))
            st += [tt, Spacer(1,5*mm)]

        st.append(Paragraph('2.   CRAC SOUMIS A VALIDER', S_H1))
        if not req.crac_soumis:
            st.append(Paragraph('Aucun CRAC en attente de validation.', S_SMALL))
        else:
            c_data = [['Collaborateur','Date de soumission']]
            for c in req.crac_soumis:
                c_data.append([c.collaborateur, c.date_soumission])
            ct = cbc_table(c_data, [90*mm, 80*mm])
            st += [ct, Spacer(1,5*mm)]

        section_num = 3

        if req.presence:
            st += _section_presence(req.presence, section_num)
            section_num += 1

        if req.stat_plan:
            sp = req.stat_plan
            st.append(Paragraph(f'{section_num}.   PLAN MARKETING {sp.annee}', S_H1))
            taux_col_plan = CBC_VERT if sp.taux_moyen >= 50 else CBC_ORANG
            pt = Table(
                [['Taux moyen','En cours','Realisees','A risque','Contraintes'],
                 [f'{sp.taux_moyen}%', str(sp.en_cours), str(sp.realisees), str(sp.a_risque), str(sp.contraintes)]],
                colWidths=[34*mm]*5, rowHeights=[10*mm, 16*mm])
            pt.setStyle(TableStyle([
                ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
                ('FONTNAME',(0,1),(-1,1),'Helvetica-Bold'),
                ('FONTSIZE',(0,0),(-1,0),8), ('FONTSIZE',(0,1),(-1,1),18),
                ('BACKGROUND',(0,0),(-1,0),CBC_GRIS), ('TEXTCOLOR',(0,0),(-1,0),BLANC),
                ('BACKGROUND',(0,1),(-1,1),colors.HexColor('#F5F6FA')),
                ('TEXTCOLOR',(0,1),(0,1), taux_col_plan),
                ('TEXTCOLOR',(1,1),(1,1), CBC_BLEU),
                ('TEXTCOLOR',(2,1),(2,1), CBC_VERT),
                ('TEXTCOLOR',(3,1),(3,1), CBC_ORANG if sp.a_risque > 0 else CBC_GRIS),
                ('TEXTCOLOR',(4,1),(4,1), CBC_ROUGE if sp.contraintes > 0 else CBC_GRIS),
                ('ALIGN',(0,0),(-1,-1),'CENTER'), ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                ('GRID',(0,0),(-1,-1),0.3,colors.HexColor('#CCCCCC')),
            ]))
            st += [pt, Spacer(1,5*mm)]

            st.append(Paragraph('Contraintes bloquantes', S_BODY))
            if not req.actions_bloquantes:
                st.append(Paragraph('Aucune contrainte active.', S_SMALL))
            else:
                b_data = [['Intitule','Responsables']]
                for a in req.actions_bloquantes:
                    b_data.append([(a.intitule or '')[:90], a.responsables or '-'])
                bt = cbc_table(b_data, [110*mm, 60*mm], wrap_cols=[0,1])
                st += [bt, Spacer(1,3*mm)]

            st.append(Paragraph('Actions a risque', S_BODY))
            if not req.actions_risque:
                st.append(Paragraph('Aucune action a risque.', S_SMALL))
            else:
                r_data = [['Intitule','Statut']]
                for a in req.actions_risque:
                    r_data.append([(a.intitule or '')[:90], STATUT_PLAN_FR.get(a.statut, a.statut)])
                rt = cbc_table(r_data, [130*mm, 40*mm], wrap_cols=[0])
                for i, a in enumerate(req.actions_risque, 1):
                    rt.setStyle(TableStyle([('TEXTCOLOR',(1,i),(1,i), CBC_ORANG)]))
                st += [rt, Spacer(1,5*mm)]

            section_num += 1

        so = req.stat_objectifs
        total_obj = so.total
        def _pct(n):
            return f'{round(n/total_obj*100)}%' if total_obj > 0 else '0%'

        st.append(Paragraph(f'{section_num}.   OBJECTIFS', S_H1))
        o_data = [
            ['Statut','Nb','%'],
            ['Atteints', str(so.atteints), _pct(so.atteints)],
            ['En cours', str(so.en_cours), _pct(so.en_cours)],
            ['Part. atteints', str(so.partiellement), _pct(so.partiellement)],
            ['Non atteints', str(so.non_atteints), _pct(so.non_atteints)],
            ['Total', str(total_obj), '100%'],
        ]
        ot = cbc_table(o_data, [90*mm, 40*mm, 40*mm])
        ot.setStyle(TableStyle([
            ('TEXTCOLOR',(0,1),(0,1),CBC_VERT),  ('FONTNAME',(0,1),(2,1),'Helvetica-Bold'),
            ('TEXTCOLOR',(0,2),(0,2),CBC_BLEU),  ('FONTNAME',(0,2),(2,2),'Helvetica-Bold'),
            ('TEXTCOLOR',(0,3),(0,3),CBC_ORANG), ('FONTNAME',(0,3),(2,3),'Helvetica-Bold'),
            ('TEXTCOLOR',(0,4),(0,4),CBC_ROUGE), ('FONTNAME',(0,4),(2,4),'Helvetica-Bold'),
            ('FONTNAME',(0,5),(-1,5),'Helvetica-Bold'),
            ('BACKGROUND',(0,5),(-1,5),colors.HexColor('#EAF0F8')),
        ]))
        st += [ot, Spacer(1,5*mm)]
        section_num += 1

        sb = req.stat_budget
        taux_exec = round(sb.total_realise / sb.total_prevu * 100) if sb.total_prevu > 0 else 0
        taux_exec_col = CBC_VERT if taux_exec >= 80 else (CBC_ORANG if taux_exec >= 50 else CBC_ROUGE)

        st.append(Paragraph(f'{section_num}.   BUDGET', S_H1))
        b_data = [
            ['Indicateur','Valeur'],
            ['Budget prevu', _formater_fcfa(sb.total_prevu)],
            ['Budget realise', _formater_fcfa(sb.total_realise)],
            ["Taux d'execution", f'{taux_exec}%'],
        ]
        bt = cbc_table(b_data, [90*mm, 80*mm])
        bt.setStyle(TableStyle([
            ('FONTNAME',(0,3),(-1,3),'Helvetica-Bold'),
            ('BACKGROUND',(0,3),(-1,3),colors.HexColor('#EAF0F8')),
            ('TEXTCOLOR',(1,3),(1,3), taux_exec_col),
        ]))
        st += [bt, Spacer(1,5*mm)]

        tmpl.build(buf, st,
                   titre='RAPPORT DE SYNTHESE - VUE SUPERVISEUR',
                   sous_titre=date_str,
                   reference=ref)

        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type='application/pdf',
            headers={'Content-Disposition': f'attachment; filename="Rapport_Superviseur_{req.date}.pdf"'}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════
# NOUVEAU — /rapport/produit
# Fiche individuelle d'un produit bancaire (KPIs 4 quadrants +
# actions en cours + chef de produit)
# ══════════════════════════════════════════════════════════════════

@app.post("/rapport/produit")
def generer_rapport_produit(req: RapportProduitRequest):
    """Génère la fiche PDF d'un produit bancaire (trame CBC officielle)."""
    try:
        buf = io.BytesIO()
        tmpl = CBCTemplate()

        p = req.produit
        k = req.kpis
        ref = f"PM-PROD-{(p.code or 'XX').upper()}-{req.periode}"
        st = []

        # ── 1. Identité du produit ────────────────────────────
        st.append(Paragraph('1.   IDENTITE DU PRODUIT', S_H1))

        statut_label = STATUT_PRODUIT_FR.get(p.statut or '', p.statut or '—')
        chefs_str = ', '.join(
            f"{c.prenom or ''} {c.nom or ''}".strip()
            for c in req.chefs_produit
        ) or '—'

        id_data = [
            ['Champ', 'Valeur'],
            ['Code produit', p.code or '—'],
            ['Libelle', p.libelle or '—'],
            ['Gamme', p.gamme or '—'],
            ['Statut', statut_label],
            ['Date de lancement', p.date_lancement or '—'],
            ['Chef(s) de produit', chefs_str],
        ]
        it = cbc_table(id_data, [60*mm, 114*mm], wrap_cols=[1])
        statut_color = STATUT_PRODUIT_COLOR.get(p.statut or '', CBC_GRIS)
        it.setStyle(TableStyle([
            ('TEXTCOLOR', (1, 4), (1, 4), statut_color),
            ('FONTNAME',  (1, 4), (1, 4), 'Helvetica-Bold'),
        ]))
        st += [it, Spacer(1, 5*mm)]

        if p.description:
            st.append(Paragraph(f'Description : {p.description}', S_SMALL))
            st.append(Spacer(1, 4*mm))

        # ── 2. KPIs — Performance Commerciale ────────────────
        st.append(Paragraph('2.   PERFORMANCE COMMERCIALE', S_H1))
        if k:
            taux_pnb = None
            if k.pnb_objectif and k.pnb_objectif > 0:
                taux_pnb = round((k.pnb_realise or 0) / k.pnb_objectif * 100)
            taux_col = CBC_VERT if (taux_pnb or 0) >= 100 else (CBC_ORANG if (taux_pnb or 0) >= 75 else CBC_ROUGE)

            pc_data = [
                ['Indicateur', 'Valeur', 'Indicateur', 'Valeur'],
                ['PNB Realise',   _formater_millions(k.pnb_realise) + ' F',
                 'PNB Objectif',  _formater_millions(k.pnb_objectif) + ' F'],
                ['Ventes nettes', _int_str(k.ventes_nettes),
                 'Commissions',   _formater_millions(k.commissions_cumul) + ' F'],
                ['Taux realisation PNB',
                 f'{taux_pnb}%' if taux_pnb is not None else '—', '', ''],
            ]
            pct = cbc_table(pc_data, [50*mm, 37*mm, 50*mm, 37*mm], wrap_cols=[0,2])
            if taux_pnb is not None:
                pct.setStyle(TableStyle([
                    ('TEXTCOLOR', (1, 3), (1, 3), taux_col),
                    ('FONTNAME',  (1, 3), (1, 3), 'Helvetica-Bold'),
                    ('FONTSIZE',  (1, 3), (1, 3), 13),
                    ('SPAN', (1, 3), (3, 3)),
                ]))
            st += [pct, Spacer(1, 5*mm)]
        else:
            st.append(Paragraph('Aucune donnee disponible pour cette periode.', S_SMALL))
            st.append(Spacer(1, 4*mm))

        # ── 3. KPIs — Usage & Portefeuille Clients ───────────
        st.append(Paragraph('3.   USAGE & PORTEFEUILLE CLIENTS', S_H1))
        if k:
            cl_data = [
                ['Indicateur', 'Valeur', 'Indicateur', 'Valeur'],
                ['Clients actifs',    _int_str(k.nb_clients_actifs),
                 'Taux actifs',       _pct_str(k.taux_actifs)],
                ['Taux inactifs',     _pct_str(k.taux_inactifs),
                 'Activation 30j',    _pct_str(k.taux_activation_30j)],
                ['Retention',         _pct_str(k.taux_retention),
                 'Cross-sell ratio',  _pct_str(k.cross_sell_ratio)],
            ]
            cl_t = cbc_table(cl_data, [50*mm, 37*mm, 50*mm, 37*mm])
            st += [cl_t, Spacer(1, 5*mm)]
        else:
            st.append(Paragraph('Aucune donnee disponible pour cette periode.', S_SMALL))
            st.append(Spacer(1, 4*mm))

        # ── 4. KPIs — Qualité & Conformité ───────────────────
        st.append(Paragraph('4.   QUALITE & CONFORMITE', S_H1))
        if k:
            conf_label = CONFORMITE_FR.get(k.conformite_produit or '', k.conformite_produit or '—')
            conf_color = CONFORMITE_COLOR.get(k.conformite_produit or '', CBC_GRIS)

            qc_data = [
                ['Indicateur', 'Valeur', 'Indicateur', 'Valeur'],
                ['Respect SLA',      _pct_str(k.respect_sla),
                 'Nb anomalies',     _int_str(k.nb_anomalies)],
                ['Taux litiges',     _pct_str(k.taux_litiges),
                 'Conformite',       conf_label],
            ]
            qct = cbc_table(qc_data, [50*mm, 37*mm, 50*mm, 37*mm])
            qct.setStyle(TableStyle([
                ('TEXTCOLOR', (3, 2), (3, 2), conf_color),
                ('FONTNAME',  (3, 2), (3, 2), 'Helvetica-Bold'),
            ]))
            st += [qct, Spacer(1, 5*mm)]
        else:
            st.append(Paragraph('Aucune donnee disponible pour cette periode.', S_SMALL))
            st.append(Spacer(1, 4*mm))

        # ── 5. KPIs — Pilotage ────────────────────────────────
        st.append(Paragraph('5.   PILOTAGE', S_H1))
        if k:
            av = k.taux_avancement_global
            av_col = CBC_VERT if (av or 0) >= 80 else (CBC_ORANG if (av or 0) >= 50 else CBC_ROUGE)
            pi_data = [
                ['Indicateur', 'Valeur', 'Indicateur', 'Valeur'],
                ['Actions en cours',     _int_str(k.nb_actions_en_cours),
                 'Avancement global',    _pct_str(av)],
            ]
            pit = cbc_table(pi_data, [50*mm, 37*mm, 50*mm, 37*mm])
            pit.setStyle(TableStyle([
                ('TEXTCOLOR', (3, 1), (3, 1), av_col),
                ('FONTNAME',  (3, 1), (3, 1), 'Helvetica-Bold'),
            ]))
            st += [pit, Spacer(1, 5*mm)]
        else:
            st.append(Paragraph('Aucune donnee disponible pour cette periode.', S_SMALL))
            st.append(Spacer(1, 4*mm))

        # ── 6. Actions en cours ───────────────────────────────
        st.append(Paragraph('6.   ACTIONS EN COURS', S_H1))
        if not req.actions_en_cours:
            st.append(Paragraph('Aucune action en cours pour ce produit.', S_SMALL))
        else:
            ac_data = [['Titre', 'Type', 'Priorite', 'Echeance', 'Responsable']]
            for a in req.actions_en_cours:
                ac_data.append([
                    (a.titre or '')[:80],
                    TYPE_ACTION_FR.get(a.type or '', a.type or '—'),
                    PRIORITE_FR.get(a.priorite or '', a.priorite or '—'),
                    a.date_echeance or '—',
                    (a.responsable or '—')[:30],
                ])
            act = cbc_table(ac_data, [60*mm, 18*mm, 18*mm, 22*mm, 36*mm], wrap_cols=[0])
            for i, a in enumerate(req.actions_en_cours, 1):
                pc = PRIORITE_COLOR.get(a.priorite or '', CBC_GRIS)
                act.setStyle(TableStyle([
                    ('TEXTCOLOR', (2, i), (2, i), pc),
                    ('FONTNAME',  (2, i), (2, i), 'Helvetica-Bold'),
                ]))
            st += [act, Spacer(1, 5*mm)]

        # ── Build ─────────────────────────────────────────────
        tmpl.build(
            buf, st,
            titre=f'FICHE PRODUIT — {(p.libelle or "").upper()}',
            sous_titre=f'Periode : {req.periode_label} — Gamme : {p.gamme or "—"}',
            reference=ref,
        )
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type='application/pdf',
            headers={
                'Content-Disposition':
                    f'attachment; filename="Fiche_Produit_{p.code or "PM"}_{req.periode}.pdf"'
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════
# NOUVEAU — /rapport/portefeuille-pm
# Rapport consolidé de tous les chefs de produit (vue Directeur)
# ══════════════════════════════════════════════════════════════════

@app.post("/rapport/portefeuille-pm")
def generer_rapport_portefeuille_pm(req: RapportPortefeuillePMRequest):
    """Génère le rapport consolidé du portefeuille PM (trame CBC officielle)."""
    try:
        buf = io.BytesIO()
        tmpl = CBCTemplate()

        ref = f"PM-PORT-{req.periode}"
        st = []

        # ── 1. Synthèse globale ───────────────────────────────
        st.append(Paragraph('1.   SYNTHESE GLOBALE', S_H1))
        s = req.synthese
        retard_col = CBC_ROUGE if s.nb_actions_en_retard > 0 else CBC_VERT

        sg = Table(
            [['Membres PM', 'Produits', 'Actions en cours', 'En retard'],
             [str(s.nb_membres), str(s.nb_produits),
              str(s.nb_actions_en_cours), str(s.nb_actions_en_retard)]],
            colWidths=[42*mm]*4, rowHeights=[10*mm, 16*mm])
        sg.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTNAME', (0,1), (-1,1), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 8),
            ('FONTSIZE', (0,1), (-1,1), 18),
            ('BACKGROUND', (0,0), (-1,0), CBC_GRIS),
            ('TEXTCOLOR',  (0,0), (-1,0), BLANC),
            ('BACKGROUND', (0,1), (-1,1), colors.HexColor('#F5F6FA')),
            ('TEXTCOLOR',  (0,1), (0,1), CBC_BLEU),
            ('TEXTCOLOR',  (1,1), (1,1), CBC_OR),
            ('TEXTCOLOR',  (2,1), (2,1), CBC_BLEU),
            ('TEXTCOLOR',  (3,1), (3,1), retard_col),
            ('ALIGN',  (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('GRID',   (0,0), (-1,-1), 0.3, colors.HexColor('#CCCCCC')),
        ]))
        st += [sg, Spacer(1, 5*mm)]

        # ── 2. Vue par chef de produit ────────────────────────
        st.append(Paragraph('2.   VUE PAR CHEF DE PRODUIT', S_H1))

        for idx, m in enumerate(req.membres, 1):
            nom_complet = f"{m.prenom or ''} {m.nom or ''}".strip() or '—'
            role_label  = ROLE_FM_FR.get(m.role_fonctionnel or '', m.role_fonctionnel or '—')

            st.append(Paragraph(
                f'{idx}.  {nom_complet} — <i>{role_label}</i> ({m.nb_produits} produit{"s" if m.nb_produits > 1 else ""})',
                S_BODY
            ))
            st.append(Spacer(1, 2*mm))

            if not m.produits:
                st.append(Paragraph('Aucun produit affecte.', S_SMALL))
                st.append(Spacer(1, 4*mm))
                continue

            p_data = [['Produit', 'Gamme', 'Statut', 'PNB Real.', 'Clients', 'SLA', 'Actions', 'Retards']]
            for p in m.produits:
                statut_label = STATUT_PRODUIT_FR.get(p.statut or '', p.statut or '—')
                p_data.append([
                    (p.libelle or '—')[:35],
                    (p.gamme or '—')[:20],
                    statut_label,
                    _formater_millions(p.pnb_realise),
                    _int_str(p.nb_clients_actifs),
                    _pct_str(p.respect_sla),
                    str(p.nb_actions_en_cours),
                    str(p.nb_actions_en_retard),
                ])

            pt = cbc_table(
                p_data,
                [38*mm, 22*mm, 20*mm, 18*mm, 14*mm, 12*mm, 14*mm, 14*mm],
                wrap_cols=[0]
            )
            for i, p in enumerate(m.produits, 1):
                sc = STATUT_PRODUIT_COLOR.get(p.statut or '', CBC_GRIS)
                rc = CBC_ROUGE if p.nb_actions_en_retard > 0 else CBC_VERT
                pt.setStyle(TableStyle([
                    ('TEXTCOLOR', (2, i), (2, i), sc),
                    ('FONTNAME',  (2, i), (2, i), 'Helvetica-Bold'),
                    ('TEXTCOLOR', (7, i), (7, i), rc),
                    ('FONTNAME',  (7, i), (7, i), 'Helvetica-Bold'),
                ]))
            st += [pt, Spacer(1, 6*mm)]

        # ── 3. Tableau récapitulatif ──────────────────────────
        st.append(Paragraph('3.   TABLEAU RECAPITULATIF PAR PRODUIT', S_H1))

        rec_data = [['Produit', 'Chef de produit', 'Statut', 'PNB Real.', 'Clients', 'Actions', 'Retards']]
        for m in req.membres:
            nom_complet = f"{m.prenom or ''} {m.nom or ''}".strip() or '—'
            for p in m.produits:
                rec_data.append([
                    (p.libelle or '—')[:35],
                    nom_complet[:25],
                    STATUT_PRODUIT_FR.get(p.statut or '', '—'),
                    _formater_millions(p.pnb_realise),
                    _int_str(p.nb_clients_actifs),
                    str(p.nb_actions_en_cours),
                    str(p.nb_actions_en_retard),
                ])

        if len(rec_data) > 1:
            rt = cbc_table(
                rec_data,
                [38*mm, 30*mm, 20*mm, 18*mm, 14*mm, 14*mm, 14*mm],
                wrap_cols=[0, 1]
            )
            for i in range(1, len(rec_data)):
                p_statut = rec_data[i][2]
                sc = STATUT_PRODUIT_COLOR.get(
                    next((k for k, v in STATUT_PRODUIT_FR.items() if v == p_statut), ''),
                    CBC_GRIS
                )
                retards = int(rec_data[i][6]) if rec_data[i][6].isdigit() else 0
                rc = CBC_ROUGE if retards > 0 else CBC_VERT
                rt.setStyle(TableStyle([
                    ('TEXTCOLOR', (2, i), (2, i), sc),
                    ('FONTNAME',  (2, i), (2, i), 'Helvetica-Bold'),
                    ('TEXTCOLOR', (6, i), (6, i), rc),
                    ('FONTNAME',  (6, i), (6, i), 'Helvetica-Bold'),
                ]))
            st += [rt, Spacer(1, 5*mm)]

        # ── Build ─────────────────────────────────────────────
        tmpl.build(
            buf, st,
            titre='RAPPORT PORTEFEUILLE PRODUCT MANAGEMENT',
            sous_titre=f'Periode : {req.periode_label} — Direction Marketing & SAV',
            reference=ref,
        )
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type='application/pdf',
            headers={
                'Content-Disposition':
                    f'attachment; filename="Rapport_Portefeuille_PM_{req.periode}.pdf"'
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
