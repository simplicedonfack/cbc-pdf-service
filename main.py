"""
CBC PDF Microservice
[MODIF 20/07] Rapport Plan Marketing : budget prévu retiré de l'AFFICHAGE
  (sous-titre + ligne du tableau de synthèse). Le champ budget_prevu reste
  REÇU du client (obligatoire, sinon 422) et conservé en base côté DIGITALIS ;
  il n'est simplement plus imprimé. Réversible : ré-ajouter les 2 lignes
  repérées "MASQUAGE BUDGET". Aucun autre rapport (superviseur, etc.) touché.
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

CBC_INDIGO = colors.HexColor('#6366F1')

# ── Modèles de données existants ───────────────────────────────

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

# ── Modèles Product Management ─────────────────────────────────

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

# ── Modèles Fiche Guide Produit ────────────────────────────────

class LigneContenu(BaseModel):
    cle: str
    valeur: str

class PJRubrique(BaseModel):
    nom: str
    type: Optional[str] = None

class RubriqueGuide(BaseModel):
    numero: int
    titre: str
    complete: bool
    updated_at: Optional[str] = None
    lignes: List[LigneContenu] = []
    pj: List[PJRubrique] = []

class FicheInfo(BaseModel):
    statut: str
    version: int
    validee_le: Optional[str] = None

class RapportFicheGuideProduitRequest(BaseModel):
    type: str = "fiche_guide_produit"
    produit: ProduitInfo
    fiche: FicheInfo
    chefs_produit: List[ChefProduit] = []
    rubriques: List[RubriqueGuide] = []
    nb_completes: int = 0
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

def _formater_millions(montant) -> str:
    if montant is None:
        return '—'
    if montant >= 1_000_000:
        return f"{montant/1_000_000:.1f} M"
    if montant >= 1_000:
        return f"{montant/1_000:.0f} K"
    return f"{montant:,.0f}"

def _pct_str(val) -> str:
    return f"{val:.1f}%" if val is not None else '—'

def _int_str(val) -> str:
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
STATUT_FICHE_FR = {
    'brouillon': 'Brouillon', 'soumise': 'Soumise',
    'validee': 'Validee', 'rejetee': 'Rejetee',
}
STATUT_FICHE_COLOR = {
    'brouillon': CBC_GRIS, 'soumise': CBC_BLEU,
    'validee': CBC_VERT, 'rejetee': CBC_ROUGE,
}
PRIORITE_FR = {'haute': 'Haute', 'moyenne': 'Moyenne', 'basse': 'Basse'}
PRIORITE_COLOR = {'haute': CBC_ROUGE, 'moyenne': CBC_ORANG, 'basse': CBC_GRIS}
TYPE_ACTION_FR = {'tache': 'Tache', 'jalon': 'Jalon', 'incident': 'Incident', 'comite': 'Comite'}
CONFORMITE_FR = {'conforme': 'Conforme', 'en_cours': 'En cours', 'non_conforme': 'Non conforme'}
CONFORMITE_COLOR = {'conforme': CBC_VERT, 'en_cours': CBC_ORANG, 'non_conforme': CBC_ROUGE}
ROLE_FM_FR = {
    'directeur_produit': 'Directeur Produit',
    'chef_produit': 'Chef de Produit',
    'observateur': 'Observateur',
}

ICONE_PJ = {
    'application/pdf': '[PDF]',
    'application/msword': '[DOC]',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '[DOCX]',
    'application/vnd.ms-excel': '[XLS]',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '[XLSX]',
}

# ── Routes ───────────────────────────────────────────────────────

@app.get("/")
def health():
    return {"status": "ok", "service": "CBC PDF Service", "version": "1.0.0"}


@app.post("/rapport/presence")
def generer_rapport_presence(req: RapportPresenceRequest):
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
             [str(presents), str(en_repos), str(en_mission), str(conges), str(absents), str(retards), str(total), taux_str]],
            colWidths=[22*mm]*7+[24*mm], rowHeights=[10*mm, 16*mm])
        kt.setStyle(TableStyle([
            ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'), ('FONTNAME',(0,1),(-1,1),'Helvetica-Bold'),
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
        st.append(Paragraph('2.   DETAIL PAR COLLABORATEUR', S_H1))
        d_data = [['#','Nom et Prenom','Fonction','Statut','Heure','Observations']]
        for i, c in enumerate(req.collaborateurs, 1):
            d_data.append([str(i), f'{c.nom} {c.prenom}', c.role, STATUT_FR.get(c.statut, c.statut), c.heure_arrivee or '—', c.commentaire or ''])
        dt = cbc_table(d_data, [8*mm,50*mm,24*mm,22*mm,18*mm,52*mm], wrap_cols=[1,5])
        for i, c in enumerate(req.collaborateurs, 1):
            col = STATUT_COLOR.get(c.statut, CBC_GRIS)
            dt.setStyle(TableStyle([('TEXTCOLOR',(3,i),(3,i),col), ('FONTNAME',(3,i),(3,i),'Helvetica-Bold')]))
        st += [dt, Spacer(1,5*mm)]
        if req.evolution:
            st.append(Paragraph('3.   EVOLUTION DE LA PRESENCE — 7 JOURS (HORS REPOS)', S_H1))
            e_data = [['Date','Presents','Total (hors repos)','Taux']]
            for e in req.evolution:
                e_data.append([e.date, str(e.presents), str(e.total), f'{e.taux}%'])
            st += [cbc_table(e_data, [40*mm, 30*mm, 40*mm, 30*mm]), Spacer(1,5*mm)]
        tmpl.build(buf, st, titre='RAPPORT DE PRESENCE', sous_titre=f'{date_str} — Direction Marketing & SAV', reference=ref, statut=req.statut_fiche)
        buf.seek(0)
        return StreamingResponse(buf, media_type='application/pdf', headers={'Content-Disposition': f'attachment; filename="Rapport_Presence_{req.date}.pdf"'})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/rapport/plan-marketing")
def generer_rapport_plan(req: RapportPlanRequest):
    try:
        buf = io.BytesIO()
        tmpl = CBCTemplate()
        total = len(req.actions)
        realisees   = sum(1 for a in req.actions if a.statut in ('realisee_totale','realisee_partielle'))
        en_cours    = sum(1 for a in req.actions if a.statut == 'en_cours')
        a_risque    = sum(1 for a in req.actions if a.statut in ('retardee','reportee','suspendue'))
        contraintes = sum(1 for a in req.actions if a.contrainte_bloquante)
        taux_moyen  = round(sum(a.taux_realisation for a in req.actions)/total) if total > 0 else 0
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
            # MASQUAGE BUDGET : ligne 'Budget prevu' retirée du tableau de synthèse
        ]
        kt = cbc_table(k_data, [80*mm, 30*mm, 64*mm], wrap_cols=[0,2])
        taux_col = CBC_VERT if taux_moyen>=50 else CBC_ROUGE
        kt.setStyle(TableStyle([
            # MASQUAGE BUDGET : style de dernière ligne retiré (visait la ligne budget)
            ('TEXTCOLOR',(1,1),(2,1),taux_col),
        ]))
        st += [kt, Spacer(1,5*mm)]
        st.append(Paragraph('2.   PLAN D\'ACTIONS — ETAT DETAILLE', S_H1))
        d_data = [['#','Intitule','Categorie','Statut','Taux','Contrainte']]
        for a in req.actions:
            d_data.append([str(a.numero or ''), (a.intitule or '')[:120], CATEGORIE_FR.get(a.categorie, a.categorie), STATUT_PLAN_FR.get(a.statut, a.statut), f'{a.taux_realisation}%', 'OUI' if a.contrainte_bloquante else ''])
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
                aj_data.append([(aj.action_intitule or '')[:120], aj.type_ajustement, (aj.motif or '')[:200], aj.date_ajustement])
            st += [cbc_table(aj_data, [50*mm, 20*mm, 70*mm, 20*mm], wrap_cols=[0,2]), Spacer(1,5*mm)]
        # MASQUAGE BUDGET : sous-titre sans le budget
        tmpl.build(buf, st, titre=f'RAPPORT PLAN MARKETING {req.annee}', sous_titre=f'Version {req.version}', reference=ref)
        buf.seek(0)
        return StreamingResponse(buf, media_type='application/pdf', headers={'Content-Disposition': f'attachment; filename="Rapport_Plan_Marketing_{req.annee}.pdf"'})
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
         [str(presents), str(en_repos), str(en_mission), str(conges), str(absents), str(retards), str(total), taux_str]],
        colWidths=[22*mm]*7+[24*mm], rowHeights=[10*mm, 16*mm])
    kt.setStyle(TableStyle([
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'), ('FONTNAME',(0,1),(-1,1),'Helvetica-Bold'),
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
        d_data.append([str(i), f'{c.nom} {c.prenom}', c.role, STATUT_FR.get(c.statut, c.statut), c.heure_arrivee or '—', c.commentaire or ''])
    dt = cbc_table(d_data, [8*mm,50*mm,24*mm,22*mm,18*mm,52*mm], wrap_cols=[1,5])
    for i, c in enumerate(req.collaborateurs, 1):
        col = STATUT_COLOR.get(c.statut, CBC_GRIS)
        dt.setStyle(TableStyle([('TEXTCOLOR',(3,i),(3,i),col), ('FONTNAME',(3,i),(3,i),'Helvetica-Bold')]))
    st += [dt, Spacer(1,5*mm)]
    if req.evolution:
        st.append(Paragraph('Evolution de la presence - 7 jours (hors repos)', S_BODY))
        e_data = [['Date','Presents','Total (hors repos)','Taux']]
        for e in req.evolution:
            e_data.append([_formater_date_courte(e.date), str(e.presents), str(e.total), f'{e.taux}%'])
        st += [cbc_table(e_data, [40*mm, 30*mm, 40*mm, 30*mm]), Spacer(1,5*mm)]
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
            ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'), ('FONTNAME',(0,1),(-1,1),'Helvetica-Bold'),
            ('FONTSIZE',(0,0),(-1,0),8), ('FONTSIZE',(0,1),(-1,1),18),
            ('BACKGROUND',(0,0),(-1,0),CBC_GRIS), ('TEXTCOLOR',(0,0),(-1,0),BLANC),
            ('BACKGROUND',(0,1),(-1,1),colors.HexColor('#F5F6FA')),
            ('TEXTCOLOR',(0,1),(0,1), CBC_ROUGE if nb_retard > 0 else CBC_VERT),
            ('TEXTCOLOR',(1,1),(1,1), CBC_BLEU if nb_crac > 0 else CBC_VERT),
            ('TEXTCOLOR',(2,1),(2,1), CBC_BLEU), ('TEXTCOLOR',(3,1),(3,1), CBC_GRIS),
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
                tt.setStyle(TableStyle([('TEXTCOLOR',(2,i),(2,i), CBC_ROUGE), ('FONTNAME',(2,i),(2,i),'Helvetica-Bold')]))
            st += [tt, Spacer(1,5*mm)]
        st.append(Paragraph('2.   CRAC SOUMIS A VALIDER', S_H1))
        if not req.crac_soumis:
            st.append(Paragraph('Aucun CRAC en attente de validation.', S_SMALL))
        else:
            c_data = [['Collaborateur','Date de soumission']]
            for c in req.crac_soumis:
                c_data.append([c.collaborateur, c.date_soumission])
            st += [cbc_table(c_data, [90*mm, 80*mm]), Spacer(1,5*mm)]
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
                ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'), ('FONTNAME',(0,1),(-1,1),'Helvetica-Bold'),
                ('FONTSIZE',(0,0),(-1,0),8), ('FONTSIZE',(0,1),(-1,1),18),
                ('BACKGROUND',(0,0),(-1,0),CBC_GRIS), ('TEXTCOLOR',(0,0),(-1,0),BLANC),
                ('BACKGROUND',(0,1),(-1,1),colors.HexColor('#F5F6FA')),
                ('TEXTCOLOR',(0,1),(0,1), taux_col_plan), ('TEXTCOLOR',(1,1),(1,1), CBC_BLEU),
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
                st += [cbc_table(b_data, [110*mm, 60*mm], wrap_cols=[0,1]), Spacer(1,3*mm)]
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
        o_data = [['Statut','Nb','%'],['Atteints', str(so.atteints), _pct(so.atteints)],['En cours', str(so.en_cours), _pct(so.en_cours)],['Part. atteints', str(so.partiellement), _pct(so.partiellement)],['Non atteints', str(so.non_atteints), _pct(so.non_atteints)],['Total', str(total_obj), '100%']]
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
        b_data = [['Indicateur','Valeur'],['Budget prevu', _formater_fcfa(sb.total_prevu)],['Budget realise', _formater_fcfa(sb.total_realise)],["Taux d'execution", f'{taux_exec}%']]
        bt = cbc_table(b_data, [90*mm, 80*mm])
        bt.setStyle(TableStyle([('FONTNAME',(0,3),(-1,3),'Helvetica-Bold'),('BACKGROUND',(0,3),(-1,3),colors.HexColor('#EAF0F8')),('TEXTCOLOR',(1,3),(1,3), taux_exec_col)]))
        st += [bt, Spacer(1,5*mm)]
        tmpl.build(buf, st, titre='RAPPORT DE SYNTHESE - VUE SUPERVISEUR', sous_titre=date_str, reference=ref)
        buf.seek(0)
        return StreamingResponse(buf, media_type='application/pdf', headers={'Content-Disposition': f'attachment; filename="Rapport_Superviseur_{req.date}.pdf"'})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/rapport/produit")
def generer_rapport_produit(req: RapportProduitRequest):
    try:
        buf = io.BytesIO()
        tmpl = CBCTemplate()
        p = req.produit
        k = req.kpis
        ref = f"PM-PROD-{(p.code or 'XX').upper()}-{req.periode}"
        st = []
        st.append(Paragraph('1.   IDENTITE DU PRODUIT', S_H1))
        statut_label = STATUT_PRODUIT_FR.get(p.statut or '', p.statut or '—')
        chefs_str = ', '.join(f"{c.prenom or ''} {c.nom or ''}".strip() for c in req.chefs_produit) or '—'
        id_data = [['Champ','Valeur'],['Code produit', p.code or '—'],['Libelle', p.libelle or '—'],['Gamme', p.gamme or '—'],['Statut', statut_label],['Date de lancement', p.date_lancement or '—'],['Chef(s) de produit', chefs_str]]
        it = cbc_table(id_data, [60*mm, 114*mm], wrap_cols=[1])
        statut_color = STATUT_PRODUIT_COLOR.get(p.statut or '', CBC_GRIS)
        it.setStyle(TableStyle([('TEXTCOLOR',(1,4),(1,4),statut_color),('FONTNAME',(1,4),(1,4),'Helvetica-Bold')]))
        st += [it, Spacer(1,5*mm)]
        if p.description:
            st.append(Paragraph(f'Description : {p.description}', S_SMALL))
            st.append(Spacer(1,4*mm))
        st.append(Paragraph('2.   PERFORMANCE COMMERCIALE', S_H1))
        if k:
            taux_pnb = None
            if k.pnb_objectif and k.pnb_objectif > 0:
                taux_pnb = round((k.pnb_realise or 0) / k.pnb_objectif * 100)
            taux_col = CBC_VERT if (taux_pnb or 0) >= 100 else (CBC_ORANG if (taux_pnb or 0) >= 75 else CBC_ROUGE)
            pc_data = [['Indicateur','Valeur','Indicateur','Valeur'],['PNB Realise', _formater_millions(k.pnb_realise)+' F','PNB Objectif', _formater_millions(k.pnb_objectif)+' F'],['Ventes nettes', _int_str(k.ventes_nettes),'Commissions', _formater_millions(k.commissions_cumul)+' F'],['Taux realisation PNB', f'{taux_pnb}%' if taux_pnb is not None else '—','','']]
            pct = cbc_table(pc_data, [50*mm, 37*mm, 50*mm, 37*mm], wrap_cols=[0,2])
            if taux_pnb is not None:
                pct.setStyle(TableStyle([('TEXTCOLOR',(1,3),(1,3),taux_col),('FONTNAME',(1,3),(1,3),'Helvetica-Bold'),('FONTSIZE',(1,3),(1,3),13),('SPAN',(1,3),(3,3))]))
            st += [pct, Spacer(1,5*mm)]
        else:
            st += [Paragraph('Aucune donnee disponible pour cette periode.', S_SMALL), Spacer(1,4*mm)]
        tmpl.build(buf, st, titre=f'FICHE PRODUIT — {(p.libelle or "").upper()}', sous_titre=f'Periode : {req.periode_label} — Gamme : {p.gamme or "—"}', reference=ref)
        buf.seek(0)
        return StreamingResponse(buf, media_type='application/pdf', headers={'Content-Disposition': f'attachment; filename="Fiche_Produit_{p.code or "PM"}_{req.periode}.pdf"'})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/rapport/portefeuille-pm")
def generer_rapport_portefeuille_pm(req: RapportPortefeuillePMRequest):
    try:
        buf = io.BytesIO()
        tmpl = CBCTemplate()
        ref = f"PM-PORT-{req.periode}"
        st = []
        st.append(Paragraph('1.   SYNTHESE GLOBALE', S_H1))
        s = req.synthese
        retard_col = CBC_ROUGE if s.nb_actions_en_retard > 0 else CBC_VERT
        sg = Table(
            [['Membres PM','Produits','Actions en cours','En retard'],
             [str(s.nb_membres), str(s.nb_produits), str(s.nb_actions_en_cours), str(s.nb_actions_en_retard)]],
            colWidths=[42*mm]*4, rowHeights=[10*mm, 16*mm])
        sg.setStyle(TableStyle([
            ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'), ('FONTNAME',(0,1),(-1,1),'Helvetica-Bold'),
            ('FONTSIZE',(0,0),(-1,0),8), ('FONTSIZE',(0,1),(-1,1),18),
            ('BACKGROUND',(0,0),(-1,0),CBC_GRIS), ('TEXTCOLOR',(0,0),(-1,0),BLANC),
            ('BACKGROUND',(0,1),(-1,1),colors.HexColor('#F5F6FA')),
            ('TEXTCOLOR',(0,1),(0,1),CBC_BLEU), ('TEXTCOLOR',(1,1),(1,1),CBC_OR),
            ('TEXTCOLOR',(2,1),(2,1),CBC_BLEU), ('TEXTCOLOR',(3,1),(3,1),retard_col),
            ('ALIGN',(0,0),(-1,-1),'CENTER'), ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
            ('GRID',(0,0),(-1,-1),0.3,colors.HexColor('#CCCCCC')),
        ]))
        st += [sg, Spacer(1,5*mm)]
        tmpl.build(buf, st, titre='RAPPORT PORTEFEUILLE PRODUCT MANAGEMENT', sous_titre=f'Periode : {req.periode_label} — Direction Marketing & SAV', reference=ref)
        buf.seek(0)
        return StreamingResponse(buf, media_type='application/pdf', headers={'Content-Disposition': f'attachment; filename="Rapport_Portefeuille_PM_{req.periode}.pdf"'})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════
# NOUVEAU — /rapport/fiche-guide-produit
# Fiche Guide Produit complète — 12 rubriques structurées
# ══════════════════════════════════════════════════════════════════

@app.post("/rapport/fiche-guide-produit")
def generer_fiche_guide_produit(req: RapportFicheGuideProduitRequest):
    """Génère la Fiche Guide Produit PDF complète (12 rubriques, trame CBC officielle)."""
    try:
        buf = io.BytesIO()
        tmpl = CBCTemplate()

        p = req.produit
        f = req.fiche
        ref = f"PM-FGP-{(p.code or 'XX').upper()}-v{f.version}"

        statut_produit_label = STATUT_PRODUIT_FR.get(p.statut or '', p.statut or '—')
        statut_produit_color = STATUT_PRODUIT_COLOR.get(p.statut or '', CBC_GRIS)
        statut_fiche_label   = STATUT_FICHE_FR.get(f.statut or '', f.statut or '—')
        statut_fiche_color   = STATUT_FICHE_COLOR.get(f.statut or '', CBC_GRIS)

        chefs_str = ', '.join(
            f"{c.prenom or ''} {c.nom or ''}".strip()
            for c in req.chefs_produit
        ) or '—'

        st = []

        # ── Bloc d'identification ─────────────────────────────
        st.append(Paragraph('IDENTIFICATION DU PRODUIT', S_H1))

        id_data = [
            ['Champ', 'Valeur', 'Champ', 'Valeur'],
            ['Code produit',     p.code or '—',             'Gamme',          p.gamme or '—'],
            ['Libelle',          p.libelle or '—',          'Statut produit', statut_produit_label],
            ['Date lancement',   p.date_lancement or '—',   'Statut fiche',   f'{statut_fiche_label} — v{f.version}'],
            ['Chef(s) produit',  chefs_str,                 'Genere le',      req.genere_le],
        ]
        it = cbc_table(id_data, [28*mm, 58*mm, 28*mm, 58*mm], wrap_cols=[1, 3])
        it.setStyle(TableStyle([
            ('TEXTCOLOR', (3, 2), (3, 2), statut_produit_color),
            ('FONTNAME',  (3, 2), (3, 2), 'Helvetica-Bold'),
            ('TEXTCOLOR', (3, 3), (3, 3), statut_fiche_color),
            ('FONTNAME',  (3, 3), (3, 3), 'Helvetica-Bold'),
        ]))
        st += [it, Spacer(1, 3*mm)]

        if p.description:
            st.append(Paragraph(f'Description : {p.description}', S_SMALL))
            st.append(Spacer(1, 3*mm))

        # Barre de complétion
        pct_complete = round(req.nb_completes / 12 * 100)
        pct_col = CBC_VERT if pct_complete == 100 else (CBC_ORANG if pct_complete >= 50 else CBC_ROUGE)
        comp_data = [
            ['Completion de la fiche', f'{req.nb_completes}/12 rubriques ({pct_complete}%)'],
        ]
        ct = cbc_table(comp_data, [60*mm, 114*mm])
        ct.setStyle(TableStyle([
            ('TEXTCOLOR', (1, 0), (1, 0), pct_col),
            ('FONTNAME',  (1, 0), (1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',  (0, 0), (-1, 0), 9),
        ]))
        st += [ct, Spacer(1, 6*mm)]

        # ── 12 rubriques ─────────────────────────────────────
        for rubrique in req.rubriques:
            # Titre de rubrique
            complete_str = ' [COMPLETE]' if rubrique.complete else ' [En cours]'
            complete_col = CBC_VERT if rubrique.complete else CBC_ORANG

            st.append(Paragraph(
                f'{rubrique.numero}.   {rubrique.titre.upper()}',
                S_H1
            ))

            # Indicateur complétion
            comp_r_data = [['Statut', complete_str.strip(), 'Derniere MAJ', rubrique.updated_at or '—']]
            cr = cbc_table(comp_r_data, [20*mm, 60*mm, 25*mm, 69*mm])
            cr.setStyle(TableStyle([
                ('TEXTCOLOR', (1, 0), (1, 0), complete_col),
                ('FONTNAME',  (1, 0), (1, 0), 'Helvetica-Bold'),
                ('FONTSIZE',  (0, 0), (-1, 0), 8),
            ]))
            st += [cr, Spacer(1, 3*mm)]

            # Contenu structuré
            if rubrique.lignes:
                c_data = [['Champ', 'Contenu']]
                for ligne in rubrique.lignes:
                    cle_formattee = ligne.cle.replace('_', ' ').capitalize()
                    valeur = (ligne.valeur or '').strip()
                    # Tronquer les valeurs très longues pour le tableau
                    if len(valeur) > 400:
                        valeur = valeur[:400] + '...'
                    c_data.append([cle_formattee, valeur])
                ct_r = cbc_table(c_data, [50*mm, 124*mm], wrap_cols=[0, 1])
                st += [ct_r, Spacer(1, 3*mm)]
            else:
                st.append(Paragraph('Aucun contenu saisi pour cette rubrique.', S_SMALL))
                st.append(Spacer(1, 3*mm))

            # Pièces jointes
            if rubrique.pj:
                pj_data = [['Pieces jointes', 'Type']]
                for pj_item in rubrique.pj:
                    type_label = ICONE_PJ.get(pj_item.type or '', '[FICH]') if pj_item.type else '[FICH]'
                    pj_data.append([(pj_item.nom or '—')[:80], type_label])
                pj_t = cbc_table(pj_data, [140*mm, 34*mm], wrap_cols=[0])
                pj_t.setStyle(TableStyle([
                    ('TEXTCOLOR', (1, 1), (1, -1), CBC_OR),
                    ('FONTNAME',  (1, 1), (1, -1), 'Helvetica-Bold'),
                ]))
                st += [pj_t, Spacer(1, 3*mm)]

            st.append(Spacer(1, 4*mm))

        # ── Pied de page informationnel ───────────────────────
        st.append(HRFlowable(width='100%', thickness=0.5, color=CBC_GRIS))
        st.append(Spacer(1, 3*mm))
        st.append(Paragraph(
            f'Document genere par {req.genere_par} le {req.genere_le} — '
            f'Fiche {statut_fiche_label} Version {f.version}'
            + (f' — Validee le {f.validee_le[:10]}' if f.validee_le else ''),
            S_SMALL
        ))

        # ── Build ─────────────────────────────────────────────
        tmpl.build(
            buf, st,
            titre=f'FICHE GUIDE PRODUIT — {(p.libelle or "").upper()}',
            sous_titre=f'Gamme : {p.gamme or "—"} | Version {f.version} | {statut_fiche_label}',
            reference=ref,
        )
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type='application/pdf',
            headers={
                'Content-Disposition':
                    f'attachment; filename="Fiche_Guide_{p.code or "PM"}_v{f.version}.pdf"'
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
# ══════════════════════════════════════════════════════════════════
# AJOUT À FAIRE dans main.py du microservice PDF
# Ajouter ces modèles et cet endpoint à la suite des existants
# ══════════════════════════════════════════════════════════════════

# ── Modèles Rapport Prospection ────────────────────────────────

class StatParUser(BaseModel):
    nom: str
    agence: str
    total: int
    convertis: int
    qualifies: int
    perdus: int
    taux_conversion: int

class StatParAgence(BaseModel):
    nom: str
    total: int
    convertis: int
    qualifies: int
    taux_conversion: int

class StatParSource(BaseModel):
    source: str
    nb: int
    pct: int

class StatParSecteur(BaseModel):
    secteur: str
    nb: int
    pct: int

class StatParVille(BaseModel):
    ville: str
    nb: int
    pct: int

class TendanceMois(BaseModel):
    mois: str
    mois_label: str
    crees: int
    convertis: int
    taux: int

class StatsFiltresLabel(BaseModel):
    periode: str
    statut: str
    source: str
    secteur: Optional[str] = None

class StatsProspection(BaseModel):
    total: int
    nb_nouveaux: int
    nb_contactes: int
    nb_qualifies: int
    nb_convertis: int
    nb_perdus: int
    taux_conversion: int
    taux_qualification: int
    taux_perte: int
    delai_moyen_jours: Optional[int] = None
    nb_geolocal: int
    pct_geolocal: int
    par_user: List[StatParUser] = []
    par_agence: List[StatParAgence] = []
    par_source: List[StatParSource] = []
    par_secteur: List[StatParSecteur] = []
    par_ville: List[StatParVille] = []
    tendance_mensuelle: List[TendanceMois] = []

class RapportProspectionRequest(BaseModel):
    filtres: StatsFiltresLabel
    stats: StatsProspection
    genere_par: str
    genere_le: str


# ── Helpers couleurs taux ───────────────────────────────────────

def _taux_color(taux: int):
    if taux >= 20: return CBC_VERT
    if taux >= 10: return CBC_ORANG
    return CBC_ROUGE


# ══════════════════════════════════════════════════════════════════
# ENDPOINT /rapport/prospection
# ══════════════════════════════════════════════════════════════════

@app.post("/rapport/prospection")
def generer_rapport_prospection(req: RapportProspectionRequest):
    """Génère le rapport analytique de prospection (trame CBC officielle)."""
    try:
        buf = io.BytesIO()
        tmpl = CBCTemplate()
        s = req.stats
        f = req.filtres
        ref = f"DCEX-PROSP-{req.genere_le.replace('/', '')}"
        st = []

        # ── En-tête filtres ───────────────────────────────────
        st.append(Paragraph('PARAMETRES DU RAPPORT', S_H1))
        filt_data = [
            ['Parametre', 'Valeur'],
            ['Periode',           f.periode],
            ['Statut filtre',     f.statut],
            ['Source filtree',    f.source],
            ['Secteur filtre',    f.secteur or 'Tous'],
            ['Genere par',        req.genere_par],
            ['Genere le',         req.genere_le],
        ]
        ft = cbc_table(filt_data, [60*mm, 114*mm])
        st += [ft, Spacer(1, 6*mm)]

        # ── 1. Indicateurs clés ───────────────────────────────
        st.append(Paragraph('1.   INDICATEURS CLES', S_H1))
        taux_col = _taux_color(s.taux_conversion)

        kpi = Table(
            [
                ['Total',     'Convertis', 'Taux conv.', 'Taux qual.', 'Taux perte', 'Geolocalises'],
                [
                    str(s.total),
                    str(s.nb_convertis),
                    f'{s.taux_conversion}%',
                    f'{s.taux_qualification}%',
                    f'{s.taux_perte}%',
                    f'{s.nb_geolocal} ({s.pct_geolocal}%)',
                ]
            ],
            colWidths=[28*mm, 28*mm, 28*mm, 28*mm, 28*mm, 34*mm],
            rowHeights=[10*mm, 16*mm]
        )
        kpi.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('FONTSIZE', (0, 1), (-1, 1), 14),
            ('BACKGROUND', (0, 0), (-1, 0), CBC_GRIS),
            ('TEXTCOLOR',  (0, 0), (-1, 0), BLANC),
            ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#F5F6FA')),
            ('TEXTCOLOR',  (0, 1), (0, 1), CBC_BLEU),
            ('TEXTCOLOR',  (1, 1), (1, 1), CBC_VERT),
            ('TEXTCOLOR',  (2, 1), (2, 1), taux_col),
            ('TEXTCOLOR',  (3, 1), (3, 1), CBC_INDIGO),
            ('TEXTCOLOR',  (4, 1), (4, 1), CBC_ROUGE),
            ('TEXTCOLOR',  (5, 1), (5, 1), CBC_BLEU),
            ('ALIGN',  (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID',   (0, 0), (-1, -1), 0.3, colors.HexColor('#CCCCCC')),
        ]))
        st += [kpi, Spacer(1, 3*mm)]

        # Délai moyen
        if s.delai_moyen_jours is not None:
            st.append(Paragraph(
                f'Delai moyen de conversion : <b>{s.delai_moyen_jours} jours</b>',
                S_BODY
            ))
        st.append(Spacer(1, 5*mm))

        # ── 2. Répartition par statut ─────────────────────────
        st.append(Paragraph('2.   REPARTITION PAR STATUT', S_H1))
        statut_data = [['Statut', 'Nb prospects', '% du total']]
        statut_rows = [
            ('Nouveau',  s.nb_nouveaux,  CBC_BLEU),
            ('Contacte', s.nb_contactes, CBC_ORANG),
            ('Qualifie', s.nb_qualifies, CBC_INDIGO),
            ('Converti', s.nb_convertis, CBC_VERT),
            ('Perdu',    s.nb_perdus,    CBC_GRIS),
        ]
        for label, nb, _ in statut_rows:
            pct_val = round(nb / s.total * 100) if s.total > 0 else 0
            statut_data.append([label, str(nb), f'{pct_val}%'])

        st_t = cbc_table(statut_data, [80*mm, 50*mm, 44*mm])
        for i, (_, _, col) in enumerate(statut_rows, 1):
            st_t.setStyle(TableStyle([('TEXTCOLOR', (0, i), (0, i), col), ('FONTNAME', (0, i), (0, i), 'Helvetica-Bold')]))
        st += [st_t, Spacer(1, 5*mm)]

        # ── 3. Tendance mensuelle ─────────────────────────────
        if s.tendance_mensuelle:
            st.append(Paragraph('3.   TENDANCE MENSUELLE', S_H1))
            tend_data = [['Mois', 'Crees', 'Convertis', 'Taux conversion']]
            for t in s.tendance_mensuelle:
                tend_data.append([t.mois_label, str(t.crees), str(t.convertis), f'{t.taux}%'])
            tend_t = cbc_table(tend_data, [60*mm, 30*mm, 30*mm, 54*mm])
            for i, t in enumerate(s.tendance_mensuelle, 1):
                col = _taux_color(t.taux)
                tend_t.setStyle(TableStyle([('TEXTCOLOR', (3, i), (3, i), col), ('FONTNAME', (3, i), (3, i), 'Helvetica-Bold')]))
            st += [tend_t, Spacer(1, 5*mm)]

        # ── 4. Performance par commercial ─────────────────────
        if s.par_user:
            st.append(Paragraph('4.   PERFORMANCE PAR COMMERCIAL', S_H1))
            user_data = [['Commercial', 'Agence', 'Total', 'Convertis', 'Qualifies', 'Perdus', 'Taux conv.']]
            for u in s.par_user:
                user_data.append([
                    u.nom[:28], u.agence[:22],
                    str(u.total), str(u.convertis), str(u.qualifies), str(u.perdus),
                    f'{u.taux_conversion}%'
                ])
            ut = cbc_table(user_data, [42*mm, 36*mm, 14*mm, 16*mm, 16*mm, 14*mm, 18*mm], wrap_cols=[0, 1])
            for i, u in enumerate(s.par_user, 1):
                col = _taux_color(u.taux_conversion)
                ut.setStyle(TableStyle([('TEXTCOLOR', (6, i), (6, i), col), ('FONTNAME', (6, i), (6, i), 'Helvetica-Bold')]))
            st += [ut, Spacer(1, 5*mm)]

        # ── 5. Performance par agence ─────────────────────────
        if s.par_agence:
            st.append(Paragraph('5.   PERFORMANCE PAR AGENCE', S_H1))
            ag_data = [['Agence', 'Total', 'Convertis', 'Qualifies', 'Taux conversion']]
            for a in s.par_agence:
                ag_data.append([a.nom[:40], str(a.total), str(a.convertis), str(a.qualifies), f'{a.taux_conversion}%'])
            agt = cbc_table(ag_data, [70*mm, 20*mm, 22*mm, 22*mm, 40*mm], wrap_cols=[0])
            for i, a in enumerate(s.par_agence, 1):
                col = _taux_color(a.taux_conversion)
                agt.setStyle(TableStyle([('TEXTCOLOR', (4, i), (4, i), col), ('FONTNAME', (4, i), (4, i), 'Helvetica-Bold')]))
            st += [agt, Spacer(1, 5*mm)]

        # ── 6. Par source ─────────────────────────────────────
        if s.par_source:
            st.append(Paragraph('6.   REPARTITION PAR SOURCE', S_H1))
            src_data = [['Source', 'Nb prospects', '% du total']]
            for src in s.par_source:
                src_data.append([src.source or 'Non renseignee', str(src.nb), f'{src.pct}%'])
            st += [cbc_table(src_data, [90*mm, 40*mm, 44*mm]), Spacer(1, 5*mm)]

        # ── 7. Par secteur ────────────────────────────────────
        if s.par_secteur:
            st.append(Paragraph('7.   REPARTITION PAR SECTEUR D\'ACTIVITE', S_H1))
            sec_data = [["Secteur d'activite", 'Nb prospects', '% du total']]
            for sec in s.par_secteur:
                sec_data.append([sec.secteur or 'Non renseigne', str(sec.nb), f'{sec.pct}%'])
            st += [cbc_table(sec_data, [100*mm, 40*mm, 34*mm], wrap_cols=[0]), Spacer(1, 5*mm)]

        # ── 8. Par ville ──────────────────────────────────────
        if s.par_ville:
            st.append(Paragraph('8.   REPARTITION PAR VILLE (TOP 10)', S_H1))
            vil_data = [['Ville', 'Nb prospects', '% du total']]
            for v in s.par_ville:
                vil_data.append([v.ville or 'Non renseignee', str(v.nb), f'{v.pct}%'])
            st += [cbc_table(vil_data, [90*mm, 40*mm, 44*mm]), Spacer(1, 5*mm)]

        # ── Build ─────────────────────────────────────────────
        tmpl.build(
            buf, st,
            titre='RAPPORT ANALYTIQUE — PROSPECTION',
            sous_titre=f'Periode : {f.periode} — {req.genere_par}',
            reference=ref,
        )
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type='application/pdf',
            headers={
                'Content-Disposition':
                    f'attachment; filename="Rapport_Prospection_{req.genere_le.replace("/", "")}.pdf"'
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# AJOUT 20/07 — ENDPOINT /rapport/activites-imprevues (AIM)
# Étape 5c : rapport des activités imprévues, trame CBC.
# Réutilise app, CBCTemplate, cbc_table, S_H1/S_BODY/S_SMALL et les
# couleurs CBC déjà importés en tête de fichier. CBC_INDIGO est défini
# ligne 34. Ajouté à la fin sans rien modifier de l'existant.
# ============================================================

class ActiviteImprevueAim(BaseModel):
    titre: str
    origine: Optional[str] = None
    statut: str
    charge_estimee_jours: Optional[float] = None
    porteur: Optional[str] = None
    periode_debut: Optional[str] = None
    periode_fin: Optional[str] = None
    commentaire_comark: Optional[str] = None

class ImpactAim(BaseModel):
    imprevue_titre: str
    type_impact: str
    action_intitule: str
    justification: Optional[str] = None
    date_effet: Optional[str] = None

class DecisionComarkAim(BaseModel):
    date_ajustement: str
    session_label: Optional[str] = None
    type_ajustement: str
    action_intitule: str
    ancien_statut: Optional[str] = None
    nouveau_statut: Optional[str] = None
    motif: Optional[str] = None

class SyntheseAim(BaseModel):
    total_imprevues: int
    integrees: int
    rejetees: int
    en_attente: int
    taux_imprevu: int
    actions_imprevues: int
    total_actions: int
    charge_declaree: float
    charge_integree: float
    actions_sacrifiees: int
    nb_impacts: int

class RapportAimRequest(BaseModel):
    annee: int
    titre: str
    version: str
    synthese: SyntheseAim
    imprevues: List[ActiviteImprevueAim] = []
    impacts: List[ImpactAim] = []
    decisions: List[DecisionComarkAim] = []
    lecture_manageriale: Optional[str] = None
    genere_le: Optional[str] = None


AIM_STATUT_FR = {
    'declaree': 'Declaree', 'qualifiee': 'Qualifiee', 'soumise': 'Soumise COMARK',
    'validee': 'Validee', 'rejetee': 'Rejetee', 'integree': 'Integree au plan',
}
AIM_STATUT_COLOR = {
    'declaree': CBC_GRIS, 'qualifiee': CBC_BLEU, 'soumise': CBC_ORANG,
    'validee': CBC_VERT, 'rejetee': CBC_ROUGE, 'integree': CBC_INDIGO,
}
AIM_TYPE_IMPACT_FR = {
    'declassement': 'Declassement', 'suspension': 'Suspension',
    'annulation': 'Annulation', 'report': 'Report',
}
AIM_TYPE_IMPACT_COLOR = {
    'declassement': CBC_ORANG, 'suspension': CBC_ORANG,
    'annulation': CBC_ROUGE, 'report': CBC_BLEU,
}
AIM_AJUSTEMENT_FR = {
    'report': 'Report', 'suspension': 'Suspension', 'annulation': 'Annulation',
    'declassement': 'Declassement', 'ajout': 'Ajout au plan',
    'remplacement': 'Remplacement', 'revision_budget': 'Revision budget',
    'revision_objectif': 'Revision objectif',
    'revision_responsable': 'Revision responsable', 'autre': 'Autre',
}


@app.post("/rapport/activites-imprevues")
def generer_rapport_aim(req: RapportAimRequest):
    """Génère le rapport Activités Imprévues (AIM) avec la trame CBC officielle."""
    try:
        buf = io.BytesIO()
        tmpl = CBCTemplate()
        s = req.synthese
        ref = f"DMSAV-AIM-{req.annee}"
        st = []

        # ── 1. Synthèse globale ───────────────────────────────
        st.append(Paragraph('1.   SYNTHESE GLOBALE', S_H1))
        taux_col = CBC_ROUGE if s.taux_imprevu > 25 else CBC_VERT
        attente_col = CBC_ORANG if s.en_attente > 0 else CBC_GRIS
        sacrif_col = CBC_ORANG if s.actions_sacrifiees > 0 else CBC_GRIS

        kpi = Table(
            [
                ['Declarees', 'Integrees', 'En attente', "Taux d'imprevu", 'Charge decl.', 'Sacrifiees'],
                [
                    str(s.total_imprevues),
                    str(s.integrees),
                    str(s.en_attente),
                    f'{s.taux_imprevu}%',
                    f'{s.charge_declaree:.0f} j',
                    str(s.actions_sacrifiees),
                ]
            ],
            colWidths=[28*mm, 28*mm, 28*mm, 30*mm, 28*mm, 28*mm],
            rowHeights=[10*mm, 16*mm]
        )
        kpi.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('FONTSIZE', (0, 1), (-1, 1), 14),
            ('BACKGROUND', (0, 0), (-1, 0), CBC_GRIS),
            ('TEXTCOLOR',  (0, 0), (-1, 0), BLANC),
            ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#F5F6FA')),
            ('TEXTCOLOR',  (0, 1), (0, 1), CBC_GRIS),
            ('TEXTCOLOR',  (1, 1), (1, 1), CBC_INDIGO),
            ('TEXTCOLOR',  (2, 1), (2, 1), attente_col),
            ('TEXTCOLOR',  (3, 1), (3, 1), taux_col),
            ('TEXTCOLOR',  (4, 1), (4, 1), CBC_BLEU),
            ('TEXTCOLOR',  (5, 1), (5, 1), sacrif_col),
            ('ALIGN',  (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID',   (0, 0), (-1, -1), 0.3, colors.HexColor('#CCCCCC')),
        ]))
        st += [kpi, Spacer(1, 3*mm)]

        st.append(Paragraph(
            f"Taux d'imprevu : <b>{s.actions_imprevues}</b> action(s) d'origine imprevue "
            f"sur <b>{s.total_actions}</b> actions au plan. "
            f"Charge integree : <b>{s.charge_integree:.0f} j</b> sur {s.charge_declaree:.0f} j declares. "
            f"Rejets : <b>{s.rejetees}</b>. Impacts qualifies : <b>{s.nb_impacts}</b>.",
            S_BODY
        ))
        st.append(Spacer(1, 5*mm))

        # ── 2. Activités imprévues — état détaillé ────────────
        st.append(Paragraph('2.   ACTIVITES IMPREVUES — ETAT DETAILLE', S_H1))
        if req.imprevues:
            d_data = [['Titre', 'Origine', 'Statut', 'Charge (j)', 'Porteur']]
            for a in req.imprevues:
                charge_str = f'{a.charge_estimee_jours:.0f}' if a.charge_estimee_jours is not None else '-'
                d_data.append([
                    (a.titre or '')[:110],
                    (a.origine or '-')[:30],
                    AIM_STATUT_FR.get(a.statut, a.statut),
                    charge_str,
                    (a.porteur or '-')[:20],
                ])
            dt = cbc_table(d_data, [76*mm, 34*mm, 28*mm, 14*mm, 22*mm], wrap_cols=[0, 1])
            for i, a in enumerate(req.imprevues, 1):
                col = AIM_STATUT_COLOR.get(a.statut, CBC_GRIS)
                dt.setStyle(TableStyle([
                    ('TEXTCOLOR', (2, i), (2, i), col),
                    ('FONTNAME',  (2, i), (2, i), 'Helvetica-Bold'),
                ]))
            st += [dt, Spacer(1, 5*mm)]
        else:
            st += [Paragraph('Aucune activite imprevue declaree.', S_SMALL), Spacer(1, 4*mm)]

        section_num = 3

        # ── 3. Matrice des impacts ────────────────────────────
        if req.impacts:
            st.append(Paragraph(f'{section_num}.   MATRICE DES IMPACTS — ACTIONS SACRIFIEES', S_H1))
            i_data = [['Activite imprevue', 'Impact', 'Action du plan impactee', 'Justification']]
            for imp in req.impacts:
                i_data.append([
                    (imp.imprevue_titre or '')[:60],
                    AIM_TYPE_IMPACT_FR.get(imp.type_impact, imp.type_impact),
                    (imp.action_intitule or '')[:70],
                    (imp.justification or '-')[:80],
                ])
            it = cbc_table(i_data, [50*mm, 24*mm, 52*mm, 48*mm], wrap_cols=[0, 2, 3])
            for i, imp in enumerate(req.impacts, 1):
                col = AIM_TYPE_IMPACT_COLOR.get(imp.type_impact, CBC_GRIS)
                it.setStyle(TableStyle([
                    ('TEXTCOLOR', (1, i), (1, i), col),
                    ('FONTNAME',  (1, i), (1, i), 'Helvetica-Bold'),
                ]))
            st += [it, Spacer(1, 5*mm)]
            section_num += 1

        # ── 4. Décisions COMARK ───────────────────────────────
        if req.decisions:
            st.append(Paragraph(f'{section_num}.   DECISIONS COMARK', S_H1))
            c_data = [['Date', 'Session', 'Type', 'Action concernee', 'Motif']]
            for d in req.decisions:
                c_data.append([
                    d.date_ajustement,
                    (d.session_label or '-')[:24],
                    AIM_AJUSTEMENT_FR.get(d.type_ajustement, d.type_ajustement),
                    (d.action_intitule or '')[:60],
                    (d.motif or '-')[:80],
                ])
            ct = cbc_table(c_data, [18*mm, 26*mm, 24*mm, 50*mm, 56*mm], wrap_cols=[3, 4])
            for i, d in enumerate(req.decisions, 1):
                col = CBC_INDIGO if d.type_ajustement == 'ajout' else CBC_ORANG
                ct.setStyle(TableStyle([
                    ('TEXTCOLOR', (2, i), (2, i), col),
                    ('FONTNAME',  (2, i), (2, i), 'Helvetica-Bold'),
                ]))
            st += [ct, Spacer(1, 5*mm)]
            section_num += 1

        # ── 5. Lecture managériale ────────────────────────────
        st.append(Paragraph(f'{section_num}.   LECTURE MANAGERIALE', S_H1))
        if req.lecture_manageriale:
            st.append(Paragraph(req.lecture_manageriale, S_BODY))
            st.append(Spacer(1, 2*mm))
        st.append(Paragraph(
            'Chaque activite imprevue integree et chaque action sacrifiee sont tracees '
            'dans la matrice des ajustements et reliees a la session COMARK ayant statue.',
            S_SMALL
        ))
        st.append(Spacer(1, 3*mm))
        if req.genere_le:
            st.append(HRFlowable(width='100%', thickness=0.5, color=CBC_GRIS))
            st.append(Spacer(1, 2*mm))
            st.append(Paragraph(f'Document genere le {req.genere_le} — Dispositif AIM / DIGITALIS CRM', S_SMALL))

        # ── Build ─────────────────────────────────────────────
        tmpl.build(
            buf, st,
            titre=f'RAPPORT ACTIVITES IMPREVUES — PLAN MARKETING {req.annee}',
            sous_titre=f'Version {req.version} — Dispositif de gestion des imprevus valide COMARK',
            reference=ref,
        )
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type='application/pdf',
            headers={
                'Content-Disposition':
                    f'attachment; filename="Rapport_AIM_Plan_Marketing_{req.annee}_CBC.pdf"'
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
