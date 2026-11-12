WITH spine AS (
    {% if target.type == 'snowflake' %}
    SELECT DATEADD(DAY, SEQ4(), '2024-01-01'::DATE) AS date_day
    FROM TABLE(GENERATOR(rowcount => 1200))
    {% else %}
    SELECT CAST(gs AS DATE) AS date_day
    FROM generate_series(CAST('2024-01-01' AS DATE), CAST('2026-12-31' AS DATE), INTERVAL '1 day') AS t(gs)
    {% endif %}
)
SELECT
    date_day,
    EXTRACT(YEAR FROM date_day) AS year,
    EXTRACT(MONTH FROM date_day) AS month,
    {% if target.type == 'snowflake' %}
    MONTHNAME(date_day) AS month_name,
    DAYNAME(date_day) AS day_name,
    (DAYOFWEEKISO(date_day) >= 6) AS is_weekend
    {% elif target.type == 'duckdb' %}
    STRFTIME(date_day, '%b') AS month_name,
    STRFTIME(date_day, '%a') AS day_name,
    (ISODOW(date_day) >= 6) AS is_weekend
    {% else %}
    TO_CHAR(date_day, 'Mon') AS month_name,
    TO_CHAR(date_day, 'Dy') AS day_name,
    (EXTRACT(ISODOW FROM date_day) >= 6) AS is_weekend
    {% endif %}
FROM spine
WHERE date_day <= CAST('2026-12-31' AS DATE)
