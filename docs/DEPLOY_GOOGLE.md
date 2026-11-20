# Deploy Focs on Google Cloud (the hackathon build)

Gemini runs every AI call (`GOOGLE_ONLY=true`), the app runs on **Cloud Run** in Mumbai, and the build shows the
root-cause story only (`VITE_EDITION=roots`). Everything below runs in **Google Cloud Shell** (the `>_` button at the
top of console.cloud.google.com): gcloud is already installed there, nothing goes on your laptop. About 20 minutes.

## 1. Project and APIs (once)

```bash
gcloud config set project YOUR_PROJECT_ID
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com
gcloud artifacts repositories create focs --repository-format=docker --location=asia-south1
```

## 2. A database just for the demo (once)

Make a **new** free Supabase project (not the focs.in one: demo accounts and test traffic stay out of real data).
Supabase → Project Settings → Database → Connection string → **Session pooler** (port 5432), and put your password in it.

## 3. Secrets (once)

```bash
printf '%s' "$(openssl rand -hex 32)"            | gcloud secrets create focs-secret --data-file=-
printf '%s' 'PASTE_YOUR_GEMINI_API_KEY'            | gcloud secrets create gemini      --data-file=-
printf '%s' 'postgresql://postgres.xxxx:PASSWORD@aws-0-ap-south-1.pooler.supabase.com:5432/postgres' \
                                                   | gcloud secrets create focs-db     --data-file=-

# let Cloud Build deploy, and the running service read the secrets
PROJECT_NUMBER=$(gcloud projects describe "$(gcloud config get-value project)" --format='value(projectNumber)')
for role in roles/run.admin roles/iam.serviceAccountUser; do
  gcloud projects add-iam-policy-binding "$(gcloud config get-value project)" \
    --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" --role="$role"
done
for s in focs-secret gemini focs-db; do
  gcloud secrets add-iam-policy-binding "$s" \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" --role=roles/secretmanager.secretAccessor
done
```

Get the Gemini key at https://aistudio.google.com/apikey. Paste it only into Cloud Shell, never into a chat or a commit.

## 4. Build and deploy (every time you ship)

```bash
git clone https://github.com/Mukul07777/GOOGLE---FOCS.git && cd GOOGLE---FOCS   # first time; later: git pull
gcloud builds submit --config cloudbuild.yaml
```

It prints the service URL at the end (`https://focs-xxxx-el.a.run.app`). Then, once:

```bash
URL=$(gcloud run services describe focs --region asia-south1 --format='value(status.url)')
gcloud run services update focs --region asia-south1 --update-env-vars APP_URL=$URL
```

## 5. Demo accounts on the live site

From Cloud Shell, in the repo, against the same database (the seed runs through the app itself):

```bash
cd backend && python3 -m pip install -q -r requirements.txt
export SUPABASE_DB_URL="$(gcloud secrets versions access latest --secret=focs-db)"
export GEMINI_API_KEY="$(gcloud secrets versions access latest --secret=gemini)" GOOGLE_ONLY=true
python3 scripts/warm_chains.py          # the top JEE/NEET chapters' root-cause chains, so the first trace is instant
python3 scripts/seed_demo.py --password 'pick-a-demo-password'
```

Sign in as `demo.focs.student@example.com` with that password. Root cause opens on "Focs noticed".

## Check before judging

- `https://YOUR-URL/api/health` answers, and the AI line says Gemini.
- Practice → answer a question → Rough → write working → **Check my working** reads it (on the tablet you will demo on).
- The demo runs on the venue Wi-Fi *and* on a phone hotspot. Keep the recorded backup video on the laptop.

The service keeps one instance warm (`--min-instances=1`, about the price of a small VM while it runs). After the
event: `gcloud run services update focs --region asia-south1 --min-instances=0`.
