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
