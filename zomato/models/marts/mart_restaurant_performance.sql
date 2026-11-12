SELECT
    f.restaurant_id,
    r.restaurant_name,
    r.city,
    r.cuisine,
    COUNT(*) AS orders,
    SUM(CASE WHEN f.is_delivered THEN f.sales_amount ELSE 0 END) AS revenue,
    ROUND(CAST(AVG(f.customer_rating) AS DECIMAL(10, 2)), 2) AS avg_customer_rating,
    ROUND(CAST(AVG(f.delivery_time_min) AS DECIMAL(10, 2)), 1) AS avg_delivery_min
FROM {{ ref('fct_orders') }} f
LEFT JOIN {{ ref('dim_restaurants') }} r
    ON f.restaurant_id = r.restaurant_id
GROUP BY 1, 2, 3, 4
