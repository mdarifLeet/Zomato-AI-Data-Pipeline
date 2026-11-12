SELECT
    f_id,
    item AS food_name,
    CASE
        WHEN LOWER(CAST(veg_or_non_veg AS VARCHAR)) = 'veg' THEN 'Veg'
        WHEN LOWER(CAST(veg_or_non_veg AS VARCHAR)) = 'non-veg' THEN 'Non-veg'
        ELSE CAST(veg_or_non_veg AS VARCHAR)
    END AS veg_or_non_veg
FROM {{ source('raw', 'food') }}
WHERE f_id IS NOT NULL
