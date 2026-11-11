"""Verify a PostgreSQL dump in a uniquely named disposable database."""

import json
import re
import subprocess
import uuid
from pathlib import Path


def docker(*args, input_data=None):
    return subprocess.run(
        ["docker", "compose", "exec", "-T", "postgres", *args],
        input=input_data,
        capture_output=True,
        check=True,
    ).stdout


def main():
    name = "phase08_restore_" + uuid.uuid4().hex[:12]
    dump = docker("sh", "-c", 'pg_dump --format=custom -U "$POSTGRES_USER" "$POSTGRES_DB"')
    if not dump:
        raise RuntimeError("empty dump")
    created = False
    try:
        docker("sh", "-c", f'createdb -U "$POSTGRES_USER" {name}')
        created = True
        docker(
            "sh",
            "-c",
            f'pg_restore --exit-on-error --no-owner -U "$POSTGRES_USER" -d {name}',
            input_data=dump,
        )
        query = (
            "select (select count(*) from information_schema.tables "
            "where table_schema = 'public' and table_type = 'BASE TABLE'), "
            "(select count(*) from faqs), (select count(*) from documents)"
        )
        original = docker(
            "sh", "-c", 'psql -At -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "$1"', "sh", query
        )
        restored = docker(
            "sh", "-c", f'psql -At -U "$POSTGRES_USER" -d {name} -c "$1"', "sh", query
        )
        if original.strip() != restored.strip() or int(restored.split(b"|")[0]) == 0:
            raise RuntimeError("restored table count differs")
        table_query = (
            "select table_name from information_schema.tables "
            "where table_schema = 'public' and table_type = 'BASE TABLE' order by table_name"
        )
        names = (
            docker(
                "sh",
                "-c",
                'psql -At -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "$1"',
                "sh",
                table_query,
            )
            .decode()
            .splitlines()
        )
        for table in names:
            if not re.fullmatch(r"[a-z_][a-z_0-9]*", table):
                raise RuntimeError("unexpected table identifier")
            digest_query = (
                f"select md5(coalesce(string_agg(row_to_json(t)::text, '' "
                f"order by row_to_json(t)::text), '')) from public.\"{table}\" t"
            )
            src = docker(
                "sh",
                "-c",
                'psql -At -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "$1"',
                "sh",
                digest_query,
            )
            dst = docker(
                "sh", "-c", f'psql -At -U "$POSTGRES_USER" -d {name} -c "$1"', "sh", digest_query
            )
            if src.strip() != dst.strip():
                raise RuntimeError(f"restored table content differs: {table}")
        result = {
            "component": "postgres",
            "dump_bytes": len(dump),
            "tables": int(restored.split(b"|")[0]),
            "faqs": int(restored.split(b"|")[1]),
            "documents": int(restored.split(b"|")[2]),
            "table_content_hashes_checked": len(names),
            "status": "passed",
        }
        Path("reports/phases/phase-08-postgres-restore.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )
        print(json.dumps(result))
    finally:
        if created:
            docker("sh", "-c", f'dropdb --if-exists -U "$POSTGRES_USER" {name}')


if __name__ == "__main__":
    main()
