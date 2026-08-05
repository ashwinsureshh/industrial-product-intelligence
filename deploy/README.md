# Deployment

The submission requires a **single live link**, so the app ships as one
service: FastAPI serves the built SPA from its own origin alongside `/api`.

## Why not Hugging Face Spaces

The Docker SDK is a paid tier; only Static Spaces are free, and a static host
cannot run the Python backend. The `deploy/huggingface/` assets are kept in
case that changes or a paid Space becomes available.

## Render (recommended, free, no card)

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
