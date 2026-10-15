-- Canonical payment events consumed by reporting models.
select event_id, customer_id, occurred_at, status, amount_cents
from {{ ref('stg_payment_deliveries') }}
