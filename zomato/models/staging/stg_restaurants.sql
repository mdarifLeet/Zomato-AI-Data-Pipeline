SELECT
    {{ try_int('id') }} AS restaurant_id,
    name AS restaurant_name,
    TRIM(REGEXP_REPLACE(COALESCE({{ regex_extract('city', '[^,]+$') }}, CAST(city AS VARCHAR)), '-[0-9]+$', '')) AS city,
    {{ try_decimal("NULLIF(CAST(rating AS VARCHAR), '--')", 3, 1) }} AS rating,
    {{ try_int(regex_extract("REPLACE(CAST(rating_count AS VARCHAR), ',', '')", '[0-9]+')) }} AS rating_count,
    {{ try_int(regex_extract("REPLACE(CAST(cost AS VARCHAR), ',', '')", '[0-9]+')) }} AS cost_for_two,
    cuisine,
    {{ regex_extract('lic_no', '[0-9]+') }} AS license_no
FROM {{ source('raw', 'restaurants') }}
WHERE {{ try_int('id') }} IS NOT NULL
