# Technical Implementation Plan: GCP Secret Manager for GEMINI_API_KEY

**PRD**: `docs/coding_implementations/ephemeral_tokens/PRD_SECRET_MANAGER.md`
**Date**: 2026-03-15

---

## Overview

Store the Gemini API key in GCP Secret Manager and configure Cloud Run + Cloud Build to inject it as an environment variable. Zero application code changes.

---

## Phase 1: Update cloudbuild.yaml

### Current Deploy Step

The `cloudbuild.yaml` deploys to Cloud Run. The deploy step needs `--set-secrets` to inject the Secret Manager value.

### Implementation

Add `--set-secrets=GEMINI_API_KEY=GEMINI_API_KEY:latest` to the `gcloud run deploy` step in `cloudbuild.yaml`.

### Code Example

```yaml
# In the deploy step, add to the gcloud run deploy args:
'--set-secrets=GEMINI_API_KEY=GEMINI_API_KEY:latest'
```

---

## Phase 2: Create .env.example

Create a `.env.example` file documenting required environment variables, with the API key placeholder noting it should use Secret Manager in production.

```
PROJECT_ID=fuse-489616
LOCATION=global
REDIS_HOST=10.8.239.3
REDIS_PORT=6379
REDIS_DB=0
GOOGLE_APPLICATION_CREDENTIALS=
# For local development only. In production, use GCP Secret Manager.
GEMINI_API_KEY=your-gemini-developer-api-key
```

---

## Phase 3: Verify .gitignore

Ensure `.env` is in `.gitignore` so the real API key is never committed.

---

## Phase 4: GCP Setup Commands (Manual, One-Time)

Run these after the first deployment:

```bash
# 1. Create the secret
echo -n "YOUR_API_KEY" | gcloud secrets create GEMINI_API_KEY \
  --data-file=- --project=fuse-489616

# 2. Get the Cloud Run service account email
SA_EMAIL=$(gcloud run services describe fuse-service \
  --region=us-central1 --project=fuse-489616 \
  --format='value(spec.template.spec.serviceAccountName)')
# If empty, use the Compute Engine default SA:
SA_EMAIL=$(gcloud iam service-accounts list \
  --filter='displayName:Compute Engine' \
  --format='value(email)' --project=fuse-489616)

# 3. Grant access
gcloud secrets add-iam-policy-binding GEMINI_API_KEY \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor" \
  --project=fuse-489616
```

---

## Testing

### Unit Tests

| ID | Test | Pass Criteria |
|----|------|---------------|
| UT-1 | `cloudbuild.yaml` contains `--set-secrets=GEMINI_API_KEY` | grep confirms presence |
| UT-2 | `.env.example` exists with `GEMINI_API_KEY` placeholder | File exists, contains line |
| UT-3 | `.gitignore` contains `.env` | grep confirms presence |

### Integration Tests (Post-Deploy)

| ID | Test | Pass Criteria |
|----|------|---------------|
| IT-1 | Cloud Run service starts with secret injected | `curl /api/ephemeral-token` returns `{"status": "ok"}` |
| IT-2 | Token generation works end-to-end | Browser connects to Gemini via ephemeral token |
| IT-3 | Secret not in container env dump | `gcloud run services describe` shows secret reference, not plain value |

---

## Implementation Checklist

- [ ] Update `cloudbuild.yaml` with `--set-secrets`
- [ ] Create `.env.example`
- [ ] Verify `.gitignore` has `.env`
- [ ] Remove `GEMINI_API_KEY` from `.env` before committing
