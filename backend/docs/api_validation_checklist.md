# API Validation Checklist (Production Readiness)

## 1) Authentication and Authorization
- [ ] Request without `Authorization` header returns `401` with no sensitive details.
- [ ] Invalid/expired JWT returns `401`.
- [ ] JWT with unknown `sub` (missing user profile) returns `401`.
- [ ] JWT + mismatched `X-Organization-Id` returns `403` (cross-tenant scope mismatch).
- [ ] Header-based auth fallback requires both `X-User-Id` and `X-Organization-Id`.

## 2) CRUD Validation by Module

### Candidates
- [ ] `POST /candidates` creates entity with caller `organization_id`.
- [ ] `GET /candidates` only returns records in caller org.
- [ ] `GET /candidates/{id}` returns `404` for missing/out-of-org entity.
- [ ] `PUT /candidates/{id}` updates only in-org entity.

### Clients
- [ ] `POST /clients` creates entity with caller `organization_id`.
- [ ] `GET /clients` only returns in-org records.
- [ ] `GET /clients/{id}` returns `404` for missing/out-of-org entity.
- [ ] `PUT /clients/{id}` updates only in-org entity.

### Jobs
- [ ] `POST /jobs` validates `client_id` belongs to same org (FK integrity).
- [ ] `GET /jobs` only returns in-org records.
- [ ] `GET /jobs/{id}` returns `404` for missing/out-of-org entity.
- [ ] `PUT /jobs/{id}` validates `client_id` updates against same org.

### Pipelines
- [ ] `POST /pipelines` validates candidate + job are in the same org.
- [ ] Duplicate candidate/job pipeline returns `409`.
- [ ] `GET /pipelines` only returns in-org records.
- [ ] `GET /pipelines/{id}` returns `404` for missing/out-of-org entity.
- [ ] `PUT /pipelines/{id}` updates only in-org entity.

### Interviews
- [ ] `POST /interviews` validates `pipeline_id` belongs to same org.
- [ ] `GET /interviews` only returns in-org records.
- [ ] `GET /interviews/{id}` returns `404` for missing/out-of-org entity.
- [ ] `PUT /interviews/{id}` validates pipeline reassignment in same org.

## 3) Input Validation and Error Contract
- [ ] Missing required fields return `422`.
- [ ] Invalid field formats (for example invalid email/UUID) return `422`.
- [ ] Invalid enum values return `422`.
- [ ] Not found resources consistently return `404`.
- [ ] Duplicate constrained operations return `409`.
- [ ] Auth failures are split correctly: `401` (unauthenticated) vs `403` (forbidden scope).

## 4) Multi-Tenant Data Isolation
- [ ] Every list endpoint applies `organization_id` scoping.
- [ ] Every read/update endpoint enforces `organization_id` scope.
- [ ] Cross-org requests return generic errors (no owner org identifiers in response).
- [ ] Debug endpoints are disabled in production mode.

## 5) Regression Gate (Before Release)
- [ ] Automated API tests pass for `401/403/404/409/422`.
- [ ] Tenant-isolation tests pass for all entities.
- [ ] FK validation tests pass for jobs, pipelines, interviews.
- [ ] Manual smoke tests done with two organizations to confirm zero leakage.
