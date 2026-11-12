SELECT
    order_item_id,
    order_id,
    {{ try_int('r_id') }} AS restaurant_id,
    f_id,
    CAST(price AS DECIMAL(10, 2)) AS price,
    CAST(quantity AS BIGINT) AS quantity,
    CAST(line_amount AS DECIMAL(10, 2)) AS line_amount
FROM {{ source('raw', 'order_items') }}
