// CHEMIN : app/api/prospection/rapport/route.ts
// ACTION  : REMPLACER

import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'
import { NextRequest, NextResponse } from 'next/server'

const PDF_SERVICE = 'https://cbc-pdf-service-dzep.onrender.com'

export async function POST(req: NextRequest) {
  try {
    const cookieStore = cookies()
    const supabase = createServerClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
      { cookies: { get: (name) => cookieStore.get(name)?.value } }
    )

    const { data: { user } } = await supabase.auth.getUser()
    if (!user) return NextResponse.json({ error: 'Non authentifié' }, { status: 401 })

    const { data: utilisateur } = await supabase
      .from('mktg_utilisateurs')
      .select('id, nom, prenom, role')
      .eq('supabase_user_id', user.id)
      .single()

    const body = await req.json()
    const { format, filtres } = body

    // ── IDs agence si filtre agence ──────────────────────────
    let agenceUserIds: string[] | null = null
    if (filtres.agence_id) {
      const { data: usersAgence } = await supabase
        .from('mktg_utilisateurs')
        .select('id')
        .eq('agence_id', filtres.agence_id)
      agenceUserIds = (usersAgence || []).map((u: any) => u.id)
    }

    // ── Requête principale ────────────────────────────────────
    let query = supabase
      .from('mktg_prospects')
      .select(`
        id, numero_prospect, raison_sociale, secteur_activite, profession,
        contact_nom, contact_telephone, ville, quartier,
        statut, source, notes, created_at, updated_at, date_conversion,
        lat_capture, lng_capture,
        createur:mktg_utilisateurs!created_by(
          id, nom, prenom, role, agence_id,
          agence:mktg_points_de_vente!agence_id(id, nom, code)
        )
      `)
      .order('created_at', { ascending: false })

    // Filtres période
    if (filtres.date_debut) query = query.gte('created_at', filtres.date_debut)
    if (filtres.date_fin)   query = query.lte('created_at', filtres.date_fin + 'T23:59:59')

    // Filtre statut
    if (filtres.statut && filtres.statut !== 'tous') query = query.eq('statut', filtres.statut)

    // Filtre utilisateur
    if (filtres.utilisateur_id) {
      query = query.eq('created_by', filtres.utilisateur_id)
    } else if (agenceUserIds) {
      if (agenceUserIds.length > 0) query = query.in('created_by', agenceUserIds)
      else return NextResponse.json({ stats: emptyStats(), liste: [], filtresLabel: {}, genere_par: '', genere_le: '' })
    }

    // Filtre source
    if (filtres.source && filtres.source !== 'tous') query = query.eq('source', filtres.source)

    // Filtre secteur
    if (filtres.secteur_activite && filtres.secteur_activite !== 'tous') {
      query = query.eq('secteur_activite', filtres.secteur_activite)
    }

    const { data: prospects, error } = await query

    if (error) {
      console.error('Erreur Supabase:', error)
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    const liste = prospects || []
    const total = liste.length

    // ── Statistiques ──────────────────────────────────────────
    const parStatut: Record<string, number> = {}
    liste.forEach((p: any) => { parStatut[p.statut] = (parStatut[p.statut] || 0) + 1 })

    const nbConvertis  = parStatut['converti']  || 0
    const nbQualifies  = parStatut['qualifie']  || 0
    const nbContactes  = parStatut['contacte']  || 0
    const nbNouveaux   = parStatut['nouveau']   || 0
    const nbPerdus     = parStatut['perdu']     || 0

    const tauxConversion    = total > 0 ? Math.round(nbConvertis / total * 100) : 0
    const tauxQualification = total > 0 ? Math.round((nbQualifies + nbConvertis) / total * 100) : 0
    const tauxPerte         = total > 0 ? Math.round(nbPerdus / total * 100) : 0

    // Délai moyen conversion
    const convertisAvecDate = liste.filter((p: any) => p.date_conversion && p.created_at)
    const delaiMoyen = convertisAvecDate.length > 0
      ? Math.round(convertisAvecDate.reduce((acc: number, p: any) => {
          const diff = new Date(p.date_conversion).getTime() - new Date(p.created_at).getTime()
          return acc + diff / (1000 * 60 * 60 * 24)
        }, 0) / convertisAvecDate.length)
      : null

    // Par utilisateur
    const parUser: Record<string, any> = {}
    liste.forEach((p: any) => {
      const u = p.createur
      if (!u) return
      const key = u.id
      if (!parUser[key]) {
        parUser[key] = {
          nom: `${u.prenom || ''} ${u.nom || ''}`.trim(),
          agence: u.agence?.nom || '—',
          total: 0, convertis: 0, qualifies: 0, perdus: 0
        }
      }
      parUser[key].total++
      if (p.statut === 'converti') parUser[key].convertis++
      if (p.statut === 'qualifie') parUser[key].qualifies++
      if (p.statut === 'perdu')    parUser[key].perdus++
    })
    const statsParUser = Object.values(parUser)
      .map((u: any) => ({
        ...u,
        taux_conversion: u.total > 0 ? Math.round(u.convertis / u.total * 100) : 0
      }))
      .sort((a: any, b: any) => b.convertis - a.convertis)

    // Par agence
    const parAgence: Record<string, any> = {}
    liste.forEach((p: any) => {
      const agence = p.createur?.agence
      const key = agence?.id || 'inconnu'
      const nom = agence?.nom || 'Non renseignée'
      if (!parAgence[key]) parAgence[key] = { nom, total: 0, convertis: 0, qualifies: 0 }
      parAgence[key].total++
      if (p.statut === 'converti') parAgence[key].convertis++
      if (p.statut === 'qualifie') parAgence[key].qualifies++
    })
    const statsParAgence = Object.values(parAgence)
      .map((a: any) => ({
        ...a,
        taux_conversion: a.total > 0 ? Math.round(a.convertis / a.total * 100) : 0
      }))
      .sort((a: any, b: any) => b.total - a.total)

    // Par source
    const parSource: Record<string, number> = {}
    liste.forEach((p: any) => {
      const s = p.source || 'Non renseignée'
      parSource[s] = (parSource[s] || 0) + 1
    })
    const statsParSource = Object.entries(parSource)
      .map(([source, nb]) => ({ source, nb, pct: total > 0 ? Math.round(nb / total * 100) : 0 }))
      .sort((a, b) => b.nb - a.nb)

    // Par secteur
    const parSecteur: Record<string, number> = {}
    liste.forEach((p: any) => {
      const s = p.secteur_activite || 'Non renseigné'
      parSecteur[s] = (parSecteur[s] || 0) + 1
    })
    const statsParSecteur = Object.entries(parSecteur)
      .map(([secteur, nb]) => ({ secteur, nb, pct: total > 0 ? Math.round(nb / total * 100) : 0 }))
      .sort((a, b) => b.nb - a.nb)

    // Par ville
    const parVille: Record<string, number> = {}
    liste.forEach((p: any) => {
      const v = p.ville || 'Non renseignée'
      parVille[v] = (parVille[v] || 0) + 1
    })
    const statsParVille = Object.entries(parVille)
      .map(([ville, nb]) => ({ ville, nb, pct: total > 0 ? Math.round(nb / total * 100) : 0 }))
      .sort((a, b) => b.nb - a.nb)
      .slice(0, 10)

    // Géolocalisation
    const nbGeolocal = liste.filter((p: any) => p.lat_capture && p.lng_capture).length

    // Tendance mensuelle
    const parMois: Record<string, { crees: number; convertis: number }> = {}
    liste.forEach((p: any) => {
      const mois = p.created_at.substring(0, 7)
      if (!parMois[mois]) parMois[mois] = { crees: 0, convertis: 0 }
      parMois[mois].crees++
      if (p.statut === 'converti') parMois[mois].convertis++
    })
    const tendanceMensuelle = Object.entries(parMois)
      .map(([mois, d]) => ({
        mois,
        mois_label: new Date(mois + '-01').toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' }),
        crees: d.crees,
        convertis: d.convertis,
        taux: d.crees > 0 ? Math.round(d.convertis / d.crees * 100) : 0
      }))
      .sort((a, b) => a.mois.localeCompare(b.mois))

    const stats = {
      total,
      nb_nouveaux:    nbNouveaux,
      nb_contactes:   nbContactes,
      nb_qualifies:   nbQualifies,
      nb_convertis:   nbConvertis,
      nb_perdus:      nbPerdus,
      taux_conversion:    tauxConversion,
      taux_qualification: tauxQualification,
      taux_perte:         tauxPerte,
      delai_moyen_jours: delaiMoyen,
      nb_geolocal:    nbGeolocal,
      pct_geolocal:   total > 0 ? Math.round(nbGeolocal / total * 100) : 0,
      par_statut:     parStatut,
      par_user:       statsParUser,
      par_agence:     statsParAgence,
      par_source:     statsParSource,
      par_secteur:    statsParSecteur,
      par_ville:      statsParVille,
      tendance_mensuelle: tendanceMensuelle,
    }

    const filtresLabel = {
      periode: filtres.date_debut && filtres.date_fin
        ? `${new Date(filtres.date_debut).toLocaleDateString('fr-FR')} au ${new Date(filtres.date_fin).toLocaleDateString('fr-FR')}`
        : 'Toute la période',
      statut:  filtres.statut && filtres.statut !== 'tous' ? filtres.statut : 'Tous',
      source:  filtres.source && filtres.source !== 'tous' ? filtres.source : 'Toutes',
      secteur: filtres.secteur_activite && filtres.secteur_activite !== 'tous' ? filtres.secteur_activite : 'Tous',
    }

    const genere_par = utilisateur ? `${utilisateur.prenom} ${utilisateur.nom}` : 'DIGITALIS'
    const genere_le  = new Date().toLocaleDateString('fr-FR')

    // ── FORMAT EXCEL → retourne JSON ─────────────────────────
    if (format === 'excel') {
      return NextResponse.json({ stats, liste, filtresLabel, genere_par, genere_le })
    }

    // ── FORMAT PDF → microservice ─────────────────────────────
    const payload = { filtres: filtresLabel, stats, genere_par, genere_le }

    const res = await fetch(`${PDF_SERVICE}/rapport/prospection`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })

    if (!res.ok) {
      const err = await res.text()
      return NextResponse.json({ error: `Erreur PDF service: ${err}` }, { status: 500 })
    }

    const pdfBuffer = await res.arrayBuffer()
    const periode   = filtres.date_debut ? `${filtres.date_debut}_${filtres.date_fin}` : 'global'

    return new NextResponse(pdfBuffer, {
      status: 200,
      headers: {
        'Content-Type': 'application/pdf',
        'Content-Disposition': `attachment; filename="Rapport_Prospection_${periode}.pdf"`,
      },
    })
  } catch (e: any) {
    console.error('Erreur rapport prospection:', e)
    return NextResponse.json({ error: e.message }, { status: 500 })
  }
}

function emptyStats() {
  return {
    total: 0, nb_nouveaux: 0, nb_contactes: 0, nb_qualifies: 0,
    nb_convertis: 0, nb_perdus: 0, taux_conversion: 0,
    taux_qualification: 0, taux_perte: 0, delai_moyen_jours: null,
    nb_geolocal: 0, pct_geolocal: 0, par_statut: {},
    par_user: [], par_agence: [], par_source: [],
    par_secteur: [], par_ville: [], tendance_mensuelle: [],
  }
}
@app.post("/rapport/prospection")
def generer_rapport_prospection(req: RapportProspectionRequest):
