select substr(business_date, 1, 7) as business_month,
       sum(revenue_cents)::bigint as revenue_cents
from {{ ref('fct_daily_revenue') }}
group by business_month
