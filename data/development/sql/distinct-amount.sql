SELECT o.business_date, p.category, SUM(DISTINCT i.amount_cents) AS revenue_cents
FROM orders AS o
JOIN order_items AS i ON i.order_id = o.order_id
JOIN product_versions AS p ON p.product_id = i.product_id
WHERE o.status = 'completed'
GROUP BY o.business_date, p.category;
