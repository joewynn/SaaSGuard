# Customer Domain

The `customer_domain` bounded context owns the customer entity lifecycle — from signup through churn. It is the anchor that all other domains reference via `customer_id`.

## Entities

::: src.domain.customer.entities

## Value Objects

::: src.domain.customer.value_objects

## Repository Interface

::: src.domain.customer.repository
