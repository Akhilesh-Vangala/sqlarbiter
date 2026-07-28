select delivery_id, event_id, customer_id, occurred_at, received_at,
       status, cast(amount_cents as bigint) as amount_cents
from {{ ref('payment_deliveries') }}
