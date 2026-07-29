# The same pipeline on AWS

Placeholder — content is specified in `../../mini-lakehouse-tutorial-plan.md` section 6 and
should be ported here verbatim: the component mapping table, what stays byte-identical, the
five traps, which AWS shape to recommend, and the cost sketch.

The headline to lead with: **roughly 90% of what you built transfers unchanged** — every dbt
model, every test, the Parquet files and Iceberg metadata, and the training script. What
changes is endpoints, credentials, and who runs the scheduler.

The number worth remembering: at this scale S3 storage plus Athena queries run about **$6 a
month**, while an always-on MLflow tracking server runs **$96–438**. Cost in a lakehouse is
driven by what you leave running, not by what you store.
