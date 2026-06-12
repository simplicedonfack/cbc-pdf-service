# CBC PDF Service

Microservice FastAPI pour la génération de rapports PDF avec la trame officielle Commercial Bank Cameroun.

## Endpoints

- `GET /` — Health check
- `POST /rapport/presence` — Rapport de présence journalier
- `POST /rapport/plan-marketing` — Rapport Plan Marketing

## Déploiement sur Render.com

1. Créer un nouveau repo GitHub `cbc-pdf-service`
2. Pusher ce dossier
3. Sur Render.com : New → Web Service → connecter le repo
4. Build command : `pip install -r requirements.txt`
5. Start command : `uvicorn main:app --host 0.0.0.0 --port $PORT`
6. Ajouter le logo : uploader `logo-cbc.jpeg` dans le repo

## Utilisation depuis DMSAV

```typescript
const response = await fetch('https://cbc-pdf-service.onrender.com/rapport/presence', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ date, collaborateurs, ... })
})
const blob = await response.blob()
const url = URL.createObjectURL(blob)
window.open(url, '_blank')
```
