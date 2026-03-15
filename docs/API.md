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
{ "status": "ok", "version": "0.1.0" }
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

Retrieve Customer 360 profile — entity data, latest churn score, risk score, recent events summary.

---

### Executive Summaries (LLM)

#### `POST /summaries/customer`

Generate an AI executive summary for a customer account.

**Request body:**

```json
{
  "customer_id": "uuid-string",
  "audience": "csm"   // csm | executive | board
}
```

> ⚠️ **Guardrail note:** All LLM outputs are prefixed with a confidence disclaimer and must be reviewed by a human before customer-facing use.

---

## Error Codes

| Code | Meaning |
|---|---|
| 404 | Customer not found |
| 422 | Validation error (see detail field) |
| 500 | Internal server error (check logs) |
| 503 | Model not loaded (run DVC pipeline first) |
