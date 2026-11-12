SELECT
    menu_id,
    {{ try_int('r_id') }} AS restaurant_id,
    f_id,
    cuisine,
    {{ try_decimal('price', 10, 2) }} AS price
FROM {{ source('raw', 'menu') }}
WHERE {{ try_int('r_id') }} IS NOT NULL
  AND {{ try_decimal('price', 10, 2) }} > 0
