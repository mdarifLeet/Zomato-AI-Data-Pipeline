SELECT
    r.review_id,
    r.order_id,
    {{ try_int('r.user_id') }} AS customer_id,
    CAST(r.restaurant_id AS VARCHAR) AS restaurant_id,
    {{ try_int('r.rating') }} AS rating,
    CAST(r.comment AS VARCHAR) AS comment,
    CAST(r.review_date AS DATE) AS review_date,
    res.city AS city
FROM {{ source('raw', 'reviews') }} r
LEFT JOIN {{ ref('stg_restaurants') }} res
    ON {{ try_int('r.restaurant_id') }} = res.restaurant_id
WHERE r.comment IS NOT NULL
