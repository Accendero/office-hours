"""Shared Iceberg write path, used by every bronze loader.

Trino has no mount into data/ and no connector that reads ad-hoc local Parquet, so
Trino-side SQL alone cannot land files. pyiceberg (pinned in requirements.txt for
exactly this) talks to the same Nessie REST catalog directly and writes Iceberg data
files that Trino reads back immediately afterward -- one writer, one set of tables.

RISK: Nessie vends the S3 endpoint for actual data-file writes as
`http://seaweedfs:8333` (the docker-compose service name) regardless of the
s3.endpoint passed to the catalog client -- that only resolves inside the compose
network. These loaders run on the host, so we alias it to localhost in-process
(the port is already published there) rather than editing system DNS/hosts.
"""
import os
import socket

_real_getaddrinfo = socket.getaddrinfo
_HOST_ALIASES = {"seaweedfs": "127.0.0.1", "nessie": "127.0.0.1"}


def _aliased_getaddrinfo(host, *args, **kwargs):
    return _real_getaddrinfo(_HOST_ALIASES.get(host, host), *args, **kwargs)


socket.getaddrinfo = _aliased_getaddrinfo

from pyiceberg.catalog.rest import RestCatalog


def get_catalog():
    return RestCatalog(
        "lakehouse",
        uri=os.getenv("NESSIE_REST_URI", "http://localhost:19120/iceberg/main"),
        warehouse="warehouse",
        **{
            "s3.endpoint": os.getenv("S3_ENDPOINT_HOST", "http://localhost:8333"),
            "s3.access-key-id": os.getenv("S3_ACCESS_KEY", "lakehouse"),
            "s3.secret-access-key": os.getenv("S3_SECRET_KEY", "lakehouse-local-secret"),
            "s3.path-style-access": "true",
            "s3.region": os.getenv("S3_REGION", "us-east-1"),
        },
    )


def load_table(catalog, schema: str, table: str, arrow_table):
    """Create <schema>.<table> from arrow_table's schema if missing, then overwrite.

    Overwrite, not append: every loader re-globs the full contents of data/ on each
    run, so re-running `make bronze` (as `make break && make bronze` does) must
    replace bronze with what's on disk now, not duplicate rows on top of it.
    """
    catalog.create_namespace_if_not_exists(schema)
    ident = f"{schema}.{table}"
    if not catalog.table_exists(ident):
        iceberg_table = catalog.create_table(ident, schema=arrow_table.schema)
    else:
        iceberg_table = catalog.load_table(ident)
    iceberg_table.overwrite(arrow_table)
    return iceberg_table
