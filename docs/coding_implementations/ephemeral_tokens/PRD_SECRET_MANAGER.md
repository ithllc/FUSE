# PRD: GCP Secret Manager for GEMINI_API_KEY

**Issue**: #30, #31
**Status**: Draft
**Date**: 2026-03-15
**Priority**: P0 — Security (API key must not exist in code or environment files)

---

## 1. Problem Statement

The ephemeral token endpoint (`GET /api/ephemeral-token`) requires a `GEMINI_API_KEY` to generate short-lived tokens for direct browser-to-Gemini WebSocket connections. Currently this key is stored in the `.env` file locally and would need to be passed as a plain-text environment variable during Cloud Run deployment. This is insecure:

- `.env` files risk accidental commits to the public repository
- Plain-text `--set-env-vars` in deployment commands appear in shell history and CI logs
- No access auditing for who/when the key is read
- No key rotation without redeployment

## 2. Solution

Store `GEMINI_API_KEY` in **Google Cloud Secret Manager** and inject it into Cloud Run as an environment variable via `--set-secrets`. The key is:
- Encrypted at rest with Google-managed keys
- Access-controlled via IAM (only the Cloud Run service account can read it)
- Audit-logged (every access recorded in Cloud Audit Logs)
- Rotatable without redeployment (using `latest` version)

**Zero code changes required** — `os.getenv("GEMINI_API_KEY")` in `main.py` reads the injected environment variable identically whether it comes from `.env`, `--set-env-vars`, or `--set-secrets`.

## 3. User Stories

| ID | Story | Acceptance Criteria |
|----|-------|-------------------|
| US-1 | As an operator, I want the API key stored securely in GCP | Key exists only in Secret Manager, not in code, .env, or deployment scripts |
| US-2 | As an operator, I want to rotate the key without redeploying | Update secret version in Secret Manager, restart Cloud Run instance |
| US-3 | As an operator, I want to audit key access | Cloud Audit Logs show every time the key is read |

## 4. Technical Requirements

### 4.1 Secret Creation
```bash
echo -n "<GEMINI_API_KEY_VALUE>" | \
  gcloud secrets create GEMINI_API_KEY --data-file=- --project=fuse-489616
```

### 4.2 IAM Binding
```bash
gcloud secrets add-iam-policy-binding GEMINI_API_KEY \
  --member="serviceAccount:<CLOUD_RUN_SA_EMAIL>" \
  --role="roles/secretmanager.secretAccessor" \
  --project=fuse-489616
```

### 4.3 Cloud Run Integration
```bash
gcloud run services update fuse-service \
  --set-secrets="GEMINI_API_KEY=GEMINI_API_KEY:latest" \
  --region=us-central1 --project=fuse-489616
```

### 4.4 Cloud Build Integration
Update `cloudbuild.yaml` to include secret reference in the deploy step.

## 5. File Inventory

| File | Action | Description |
|------|--------|-------------|
| `cloudbuild.yaml` | Modify deploy step | Add `--set-secrets` flag |
| `.env` | Remove `GEMINI_API_KEY` line | Key moves to Secret Manager (local dev uses env var directly) |
| `.env.example` | Add placeholder | Document that key is needed |

## 6. Constraints

- Zero code changes to `main.py` — `os.getenv("GEMINI_API_KEY")` works as-is
- Local development continues to use `.env` or shell export
- Secret Manager is free for first 6 secret versions and 10,000 access operations/month
