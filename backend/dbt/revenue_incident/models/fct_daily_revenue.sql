select substr(occurred_at, 1, 10) as business_date,
       sum(amount_cents)::bigint as revenue_cents
from {{ ref('int_payment_events') }}
where status = 'completed'
group by business_date
