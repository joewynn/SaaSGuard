# API Reference

Full OpenAPI spec is auto-generated at runtime: `http://localhost:8000/docs` (Swagger UI) or `http://localhost:8000/redoc`.

## Base URL

```
Development:  http://localhost:8000
Production:   https://<your-render-url>.onrender.com
```

## Authentication

_Phase 7 addition — JWT bearer token via `Authorization: Bearer <token>` header._

---

## Endpoints

### Health

#### `GET /health`

Liveness probe. Returns 200 if the service is up.

```json
{ "status": "ok", "version": "0.7.0" }
```

#### `GET /ready`

Readiness probe. Returns 503 if model artifacts are not loaded (run `dvc pull` first).

```json
{ "status": "ready", "version": "0.7.0" }
```

**503 response:**
```json
{ "detail": "Model not loaded" }
```

---

### Predictions

#### `POST /predictions/churn`

Predict probability of churn within the next 90 days for a given customer.

**Request body:**

```json
{
  "customer_id": "uuid-string"
}
```

**Response `200`:**

```json
{
  "customer_id": "uuid-string",
  "churn_probability": 0.73,
  "confidence_interval": [0.65, 0.81],
  "top_shap_features": [
    { "feature": "days_since_last_event", "value": 14, "shap_impact": 0.22 },
    { "feature": "support_tickets_last_30d", "value": 3, "shap_impact": 0.18 }
  ],
  "recommended_action": "High risk – trigger CS outreach within 48 hours",
  "model_version": "1.0.0"
}
```

---

#### `POST /predictions/risk-score`

Compute compliance + usage risk score.

**Request body:**

```json
{
  "customer_id": "uuid-string"
}
```

**Response `200`:**

```json
{
  "customer_id": "uuid-string",
  "risk_score": 0.61,
  "risk_tier": "medium",
  "components": {
    "compliance_gap_score": 0.55,
    "vendor_risk_flags": 2,
    "usage_decay_score": 0.70
  }
}
```

---

#### `GET /predictions/batch`

Bulk scores for all active customers. Returns paginated results.

**Query params:** `page` (default 1), `page_size` (default 100, max 1000)

---

### Customers

#### `GET /customers/{customer_id}`

Retrieve full Customer 360 profile — entity data, churn prediction, SHAP drivers, usage velocity, support health, and GTM stage.

**Response `200`:**

```json
{
  "customer_id": "uuid-string",
  "plan_tier": "enterprise",
  "industry": "fintech",
  "mrr": 12500.0,
  "tenure_days": 420,
  "churn_probability": 0.72,
  "risk_tier": "HIGH",
  "top_shap_features": [
    { "feature": "events_last_30d", "value": 3.0, "shap_impact": 0.41 },
    { "feature": "open_ticket_count", "value": 4.0, "shap_impact": 0.28 }
  ],
  "events_last_30d": 3,
  "open_ticket_count": 4,
  "gtm_stage": "Renewal",
  "latest_prediction_at": "2026-03-14T12:00:00"
}
```

**404** — customer not found.

---

### Executive Summaries (LLM)

#### `POST /summaries/customer`

Generate a 3–5 sentence AI executive summary grounded in DuckDB customer data.

**Request body:**

```json
{
  "customer_id": "uuid-string",
  "audience": "csm"
}
```

**Audience values:** `csm` (tactical, action-focused) | `executive` (revenue-focused, quantified)

**Response:**

```json
{
  "customer_id": "...",
  "audience": "csm",
  "summary": "Customer X has a 72% churn probability... ⚠️ AI-generated. Requires human review.",
  "churn_probability": 0.72,
  "risk_tier": "high",
  "top_shap_features": [{"feature": "events_last_30d", "value": 3.0, "shap_impact": 0.42}],
  "confidence_score": 1.0,
  "guardrail_flags": [],
  "generated_at": "2026-03-14T12:00:00+00:00",
  "model_used": "llama-3.1-8b-instant",
  "llm_provider": "groq"
}
```

> ⚠️ **Guardrail note:** All LLM outputs include `⚠️ AI-generated. Requires human review.` and a `confidence_score`. Scores < 0.5 indicate guardrail failures and require manual review before use.

---

#### `POST /summaries/customer/ask`

Answer a free-text question about a customer using their DuckDB history as context.

**Request body:**

```json
{
  "customer_id": "uuid-string",
  "question": "Why is this customer at risk?"
}
```

**Response:**

```json
{
  "customer_id": "...",
  "question": "Why is this customer at risk?",
  "answer": "Based on available data, low events_last_30d... ⚠️ AI-generated. Requires human review.",
  "confidence_score": 1.0,
  "guardrail_flags": [],
  "scope_exceeded": false,
  "generated_at": "2026-03-14T12:00:00+00:00",
  "model_used": "llama-3.1-8b-instant",
  "llm_provider": "groq"
}
```

`scope_exceeded: true` means the question could not be answered from available customer data — no hallucinated answer is returned.

---

## Error Codes

| Code | Meaning |
|---|---|
| 404 | Customer not found |
| 422 | Validation error (see detail field) |
| 500 | Internal server error (check logs) |
| 503 | Model not loaded (run DVC pipeline first) |
