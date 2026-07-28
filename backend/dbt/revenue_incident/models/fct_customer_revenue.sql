select customer_id, sum(amount_cents)::bigint as revenue_cents
from {{ ref('int_payment_events') }}
where status = 'completed'
group by customer_id
