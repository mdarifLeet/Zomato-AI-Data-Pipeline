{% macro try_int(expr) -%}
    {%- if target.type == 'snowflake' -%}
        TRY_TO_NUMBER({{ expr }}::VARCHAR)
    {%- elif target.type == 'duckdb' -%}
        TRY_CAST({{ expr }} AS BIGINT)
    {%- else -%}
        CASE WHEN {{ expr }}::TEXT ~ '^-?[0-9]+$' THEN ({{ expr }}::TEXT)::BIGINT ELSE NULL END
    {%- endif -%}
{%- endmacro %}

{% macro try_decimal(expr, precision=10, scale=2) -%}
    {%- if target.type == 'snowflake' -%}
        TRY_TO_DECIMAL({{ expr }}::VARCHAR, {{ precision }}, {{ scale }})
    {%- elif target.type == 'duckdb' -%}
        TRY_CAST({{ expr }} AS DECIMAL({{ precision }}, {{ scale }}))
    {%- else -%}
        CASE WHEN {{ expr }}::TEXT ~ '^-?[0-9]+(\.[0-9]+)?$' THEN ({{ expr }}::TEXT)::DECIMAL({{ precision }}, {{ scale }}) ELSE NULL END
    {%- endif -%}
{%- endmacro %}

{% macro regex_extract(expr, pattern) -%}
    {%- if target.type == 'snowflake' -%}
        REGEXP_SUBSTR({{ expr }}::VARCHAR, '{{ pattern }}')
    {%- elif target.type == 'duckdb' -%}
        NULLIF(regexp_extract({{ expr }}::VARCHAR, '{{ pattern }}'), '')
    {%- else -%}
        SUBSTRING({{ expr }}::TEXT FROM '{{ pattern }}')
    {%- endif -%}
{%- endmacro %}
