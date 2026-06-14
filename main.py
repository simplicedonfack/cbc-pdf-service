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

# Couleur additionnelle pour le statut "Repos" (indigo) — cohérente avec le
# front-end (badge "Repos" en bg-indigo-100 / text-indigo-700).
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

        # Taux unifié : calculé hors collaborateurs en repos, quel que soit
        # le type de jour. None si tous les collaborateurs sont en repos.
        denom = total - en_repos
        taux  = round(presents / denom * 100) if denom > 0 else None

        # Date formatée
        try:
            d = date.fromisoformat(req.date)
            jours_fr = ['Lundi','Mardi','Mercredi','Jeudi','Vendredi','Samedi','Dimanche']
            date_str = f"{jours_fr[d.weekday()]} {d.strftime('%d/%m/%Y')}"
        except:
            date_str = req.date

        nature_str = TYPE_JOUR_FR.get(req.type_jour, req.type_jour.replace('_', ' ').capitalize())
        ref = f"DMSAV-PRES-{req.date.replace('-','')}"
        st = []

        # 1. Synthèse
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

        # 2. Détail
        st.append(Paragraph('2.   DETAIL PAR COLLABORATEUR', S_H1))
        d_data = [['#','Nom et Prenom','Fonction','Statut','Heure','Observations']]
        for i, c in enumerate(req.collaborateurs, 1):
            d_data.append([str(i), f'{c.nom} {c.prenom}', c.role,
                           STATUT_FR.get(c.statut, c.statut),
                           c.heure_arrivee or '—', c.commentaire or ''])
        # wrap_cols : Nom et Prenom (1) et Observations (5) — textes pouvant être longs
        dt = cbc_table(d_data, [8*mm,50*mm,24*mm,22*mm,18*mm,52*mm], wrap_cols=[1,5])
        for i, c in enumerate(req.collaborateurs, 1):
            col = STATUT_COLOR.get(c.statut, CBC_GRIS)
            dt.setStyle(TableStyle([
                ('TEXTCOLOR',(3,i),(3,i),col),
                ('FONTNAME',(3,i),(3,i),'Helvetica-Bold')
            ]))
        st += [dt, Spacer(1,5*mm)]

        # 3. Évolution 7 jours (hors repos)
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

        # 1. Synthèse
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
        # wrap_cols : Indicateur (0) et Commentaire (2) — libellés pouvant être longs
        kt = cbc_table(k_data, [80*mm, 30*mm, 64*mm], wrap_cols=[0,2])
        taux_col = CBC_VERT if taux_moyen>=50 else CBC_ROUGE
        kt.setStyle(TableStyle([
            ('FONTNAME',(0,-1),(-1,-1),'Helvetica-Bold'),
            ('BACKGROUND',(0,-1),(-1,-1),colors.HexColor('#EAF0F8')),
            ('TEXTCOLOR',(1,1),(2,1),taux_col),
        ]))
        st += [kt, Spacer(1,5*mm)]

        # 2. Actions détaillées
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
        # wrap_cols : Intitule (1) et Categorie (2) — textes longs sources du chevauchement
        dt = cbc_table(d_data, [8*mm, 60*mm, 28*mm, 22*mm, 12*mm, 16*mm], wrap_cols=[1,2])
        for i, a in enumerate(req.actions, 1):
            if a.contrainte_bloquante:
                dt.setStyle(TableStyle([('TEXTCOLOR',(5,i),(5,i),CBC_ROUGE),('FONTNAME',(5,i),(5,i),'Helvetica-Bold')]))
            c = CBC_VERT if a.statut in ('realisee_totale',) else (CBC_ROUGE if a.statut in ('retardee','suspendue','annulee') else CBC_GRIS)
            dt.setStyle(TableStyle([('TEXTCOLOR',(3,i),(3,i),c)]))
        st += [dt, Spacer(1,5*mm)]

        # 3. Ajustements
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
            # wrap_cols : Action concernee (0) et Motif (2) — textes longs
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
