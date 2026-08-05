# Deployment

The submission requires a **single live link**, so the app ships as one
service: FastAPI serves the built SPA from its own origin alongside `/api`.

## Why not Hugging Face Spaces

The Docker SDK is a paid tier; only Static Spaces are free, and a static host
cannot run the Python backend. The `deploy/huggingface/` assets are kept in
case that changes or a paid Space becomes available.

## Google Cloud Run (in use)

Scales to zero, wakes in 1–3 seconds, and demo traffic sits well inside the
free allowance. The same root `Dockerfile` is the deployment unit — Cloud Build
builds it, so nothing needs installing except the CLI.

**One-time setup**

Install the gcloud CLI (https://cloud.google.com/sdk/docs/install), then:

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
```

**Deploy** — run from the repository root:

```bash
gcloud run deploy product-intelligence --source . --region asia-south1 --allow-unauthenticated --memory 1Gi --cpu 1 --min-instances 0 --set-env-vars PI_ALLOW_SERVER_KEY=0,PI_ALLOW_LIVE=1,PI_CACHE_DIR=/home/app/.cache/pi
```

The command prints the public HTTPS URL. Re-running it redeploys.

Why those flags:

- `--allow-unauthenticated` — reviewers must reach it without a Google account.
- `--memory 1Gi` — the 512Mi default is tight once pdfplumber, lxml and
  pydantic are loaded; an OOM shows up as a confusing 503.
- `--min-instances 0` — scales to zero so idle time is free. Cloud Run's cold
  start is a second or two, unlike Render's ~50, so no keep-alive is needed.
  Set `--min-instances 1` in the final days before judging if you want the
  first request to be instant; it costs a little but removes the variable.
- `--region asia-south1` — Mumbai, closest to India. Any region works.
- `PI_ALLOW_SERVER_KEY=0` — the deployment cannot spend anyone's credits.

`.gcloudignore` keeps `node_modules`, caches and any `.env` out of the upload.

**Check it after deploying**

```bash
curl -s https://<your-url>/api/health
```

Expect `"status":"ok"` and a category count. Then open the URL and click
through all four tabs.

## Render (free fallback, no card)

1. Push this repo to GitHub.
2. **render.com** → *New* → *Web Service* → connect the repository.
   Render reads `render.yaml` and the root `Dockerfile` automatically.
3. Confirm the plan is **Free** and deploy. First build takes ~5–8 minutes.
4. The service is live at `https://<name>.onrender.com`.

Render authorises private repositories, so the GitHub repo can stay private
until submission.

### The cold-start problem, and the fix

A free Render service **sleeps after ~15 minutes idle** and takes roughly 50
seconds to wake. Reviewers arrive unannounced, and a blank 50-second wait reads
as a broken link rather than a sleeping one.

Keep it warm with a free external pinger — **cron-job.org**, **UptimeRobot**,
or any equivalent:

```
URL       https://<name>.onrender.com/api/health
Interval  every 10 minutes
```

`/api/health` is cheap: it returns config and cache counts and touches no
model. Set this up **before** submitting the link, not after.

## Alternatives if Render does not suit

| Host | Free tier | Cold start | Card required |
| --- | --- | --- | --- |
| Render | yes | ~50 s after idle | no |
| Google Cloud Run | generous | 1–3 s | yes |
| Fly.io | small allowance | none if kept warm | yes |
| Railway | trial credit only | none | yes |

Cloud Run is the better experience if a card is acceptable — it scales to zero
without the long wake, and the free monthly allowance comfortably covers demo
traffic.

## What the deployment can and cannot do

- **It cannot spend anyone's credits.** No server API key is configured and
  `PI_ALLOW_SERVER_KEY=0`, so a visitor selecting Live AI without supplying
  their own key is served the bundled pre-computed results or degraded to the
  demo engine — never the owner's account.
- **Live AI still shows real model output**, because pre-computed results for
  the demo products are committed to `backend/app/data/precomputed/`.
- **Uploads are bounded**: 25 MB per PDF, 250 rows per CSV or batch.
- **Learned taxonomy state is ephemeral** on a free instance. Approving a
  category persists until the next deploy or restart, which is the right
  behaviour for a demo.
