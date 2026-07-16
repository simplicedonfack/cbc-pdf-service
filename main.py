# ============================================================
# Chemin : main.py (repo du microservice cbc-pdf-service, Render)
# DIGITALIS CRM — Module Activités Imprévues (AIM)
# Étape 5c : AJOUT À FAIRE dans main.py
# Coller ces modèles et cet endpoint à la suite des existants
# (après /rapport/prospection), puis commit → Render redéploie.
# ============================================================

# ── Modèles Rapport Activités Imprévues (AIM) ──────────────────

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


# ── Helpers AIM ─────────────────────────────────────────────────

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


# ══════════════════════════════════════════════════════════════════
# ENDPOINT /rapport/activites-imprevues
# ══════════════════════════════════════════════════════════════════

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
