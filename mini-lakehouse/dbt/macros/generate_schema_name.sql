{#
  dbt's default generate_schema_name concatenates the profile's target schema with
  each model's custom +schema (e.g. target "silver" + model schema "gold" -> "silver_gold"),
  not the plain "bronze"/"silver"/"gold" every doc, script, and troubleshooting note in
  this repo assumes. Use the custom schema verbatim -- the standard override for this.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
