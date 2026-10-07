WITH latest AS (
    SELECT product_id, MAX(version) AS version
    FROM product_versions
    GROUP BY product_id
)
SELECT o.business_date, p.category, SUM(i.amount_cents) AS revenue_cents
FROM orders AS o
JOIN order_items AS i ON i.order_id = o.order_id
JOIN latest AS l ON l.product_id = i.product_id
JOIN product_versions AS p ON p.product_id = l.product_id AND p.version = l.version
WHERE o.status = 'completed'
GROUP BY o.business_date, p.category;
