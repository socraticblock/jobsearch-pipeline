"""I-29 -- the database schema pin.

`SCHEMA` and
`SCHEMA_VERSION` in
`jobsearch/db.py` are
the **database
contract**: they
define the data
layout that the
rest of the code
reads and writes.
The schema is
applied every
time `connect()`
is called, and
`SCHEMA_VERSION`
is recorded in the
`meta` table.

`SCHEMA` defines
7 tables and 3
indexes:
- `meta`:
  key/value store
  (records
  `schema_version`)
- `sources`: where
  listings came
  from
- `jobs`: canonical
  listings
- `sightings`:
  observations of
  a listing
- `messages`: M2
  processed alert
  messages
- `decisions`: M3
  owner decisions
- `actions`: M5
  outbound action
  audit

The 3 indexes:
- `idx_jobs_status`:
  on jobs(status)
- `idx_jobs_seen`:
  on
  jobs(last_seen_at)
- `idx_sightings_job`:
  on
  sightings(job_id)

`SCHEMA_VERSION = 1`
is the version
stored in the meta
table at init.

A drift in
`SCHEMA` would
silently change
the data layout:
- Drop a table ->
  the rest of the
  code would error
  on first read
  ("no such table").
- Add a column ->
  existing rows
  would have NULL
  in the new
  column.
- Drop a column ->
  the rest of the
  code would error
  on first read
  ("no such
  column").
- Drop an index ->
  queries would
  fall back to
  table scans
  (silent
  performance
  regression).

A drift in
`SCHEMA_VERSION`
would silently
mark an existing
DB as the wrong
version. If a
contributor
bumped the
version to 2
without writing a
migration, the
gate would still
work (since the
schema is the
same), but a
future migration
that checked
"if version == 1
then ..." would
silently skip the
migration.

Before this turn,
no test pinned
the schema. A
contributor who
added a column
or dropped a
table would not
see a test fail
until the next
runtime test
exercised the
new column /
dropped table.

The fix is a new
`TestDatabaseSchema`
class with 3 tests:
1. `test_schema_version_is_one`:
   `SCHEMA_VERSION`
   is exactly 1.
2. `test_schema_contains_documented_tables`:
   the schema
   contains all 7
   documented
   tables.
3. `test_schema_contains_documented_indexes`:
   the schema
   contains all 3
   documented
   indexes.

Drift-injection
verified: removing
a table from
`SCHEMA` would
fail the tables
test.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_db():
    """Helper: import the
    db module by
    exec'ing the source
    file. We must
    register the module
    in `sys.modules`
    BEFORE
    `exec_module`
    because the
    module uses type
    annotations that
    the dataclass
    decorator needs to
    walk the
    `__module__` chain
    (same lesson as
    the doctor
    module).
    """
    import importlib.util
    import sys as _sys
    p = ROOT / "jobsearch" / "db.py"
    spec = importlib.util.spec_from_file_location(
        "_db_for_schema_test", p,
    )
    mod = importlib.util.module_from_spec(spec)
    _sys.modules["_db_for_schema_test"] = mod
    spec.loader.exec_module(mod)
    return mod


class TestDatabaseSchema(unittest.TestCase):
    """`SCHEMA` and
    `SCHEMA_VERSION` in
    `jobsearch/db.py`
    are the database
    contract. A drift
    would silently
    change the data
    layout.
    """

    EXPECTED_TABLES = (
        "meta", "sources", "jobs", "sightings",
        "messages", "decisions", "actions",
    )

    EXPECTED_INDEXES = (
        "idx_jobs_status", "idx_jobs_seen",
        "idx_sightings_job",
    )

    def test_schema_version_is_one(self) -> None:
        """`SCHEMA_VERSION` in
        `jobsearch/db.py`
        must be exactly
        1. The version
        is recorded in
        the `meta` table
        at init. A
        drift to 2
        without a
        migration
        would silently
        mark an
        existing DB
        as the wrong
        version.
        """
        mod = _load_db()
        self.assertEqual(
            mod.SCHEMA_VERSION, 1,
            f"SCHEMA_VERSION is "
            f"{mod.SCHEMA_VERSION!r}, "
            f"expected 1. The version "
            f"is recorded in the `meta` "
            f"table at init. A drift "
            f"to 2 without a migration "
            f"would silently mark an "
            f"existing DB as the wrong "
            f"version."
        )
        # And it
        # must
        # be
        # an
        # int
        # (not
        # a
        # string).
        self.assertIsInstance(
            mod.SCHEMA_VERSION, int,
            f"SCHEMA_VERSION is "
            f"{type(mod.SCHEMA_VERSION).__name__}, "
            f"not an int. The version "
            f"is stored via "
            f"`str(SCHEMA_VERSION)` in "
            f"the meta table, but the "
            f"constant itself must be "
            f"an int so that future "
            f"version-comparison code "
            f"works correctly."
        )
        # And it
        # must
        # be
        # positive
        # (a
        # version
        # 0
        # would
        # be
        # invalid).
        self.assertGreater(
            mod.SCHEMA_VERSION, 0,
            f"SCHEMA_VERSION is "
            f"{mod.SCHEMA_VERSION}, "
            f"which is not positive. "
            f"A version of 0 would be "
            f"invalid; the constant is "
            f"used to track schema "
            f"version, and the first "
            f"version is 1."
        )

    def test_schema_contains_documented_tables(self) -> None:
        """`SCHEMA` in
        `jobsearch/db.py`
        must contain
        all 7 documented
        tables. A drift
        that drops a
        table would
        silently cause
        the rest of
        the code to
        error on first
        read.
        """
        mod = _load_db()
        for table in self.EXPECTED_TABLES:
            with self.subTest(table=table):
                # The
                # CREATE
                # TABLE
                # statement
                # must
                # be
                # present
                # in
                # the
                # schema.
                self.assertIn(
                    f"CREATE TABLE IF NOT EXISTS {table}",
                    mod.SCHEMA,
                    f"Table `{table}` is NOT in "
                    f"SCHEMA. The schema "
                    f"defines the data layout "
                    f"the rest of the code "
                    f"reads and writes. "
                    f"Removing a table from "
                    f"the schema would "
                    f"silently cause the "
                    f"rest of the code to "
                    f"error on first read "
                    f"('no such table')."
                )
        # And no
        # undocumented
        # tables
        # (catch
        # over-pin).
        import re as _re
        actual = set(_re.findall(
            r"CREATE TABLE IF NOT EXISTS (\w+)",
            mod.SCHEMA,
        ))
        documented = set(self.EXPECTED_TABLES)
        added = actual - documented
        self.assertEqual(
            added, set(),
            f"SCHEMA has {len(added)} "
            f"undocumented table(s): "
            f"{sorted(added)}. If a table "
            f"was intentionally added, "
            f"update EXPECTED_TABLES in "
            f"the same commit. The "
            f"schema is the data layout "
            f"the rest of the code "
            f"reads and writes; adding "
            f"an undocumented table "
            f"would silently introduce "
            f"new persistence that no "
            f"code reads or writes."
        )

    def test_schema_contains_documented_indexes(self) -> None:
        """`SCHEMA` in
        `jobsearch/db.py`
        must contain
        all 3 documented
        indexes. A
        drift that
        drops an index
        would silently
        cause queries
        to fall back
        to table scans.
        """
        mod = _load_db()
        for index in self.EXPECTED_INDEXES:
            with self.subTest(index=index):
                self.assertIn(
                    f"CREATE INDEX IF NOT EXISTS {index}",
                    mod.SCHEMA,
                    f"Index `{index}` is NOT in "
                    f"SCHEMA. The index is "
                    f"needed for query "
                    f"performance. Removing "
                    f"the index would silently "
                    f"cause queries to fall "
                    f"back to table scans."
                )
        # And no
        # undocumented
        # indexes
        # (catch
        # over-pin).
        import re as _re
        actual = set(_re.findall(
            r"CREATE INDEX IF NOT EXISTS (\w+)",
            mod.SCHEMA,
        ))
        documented = set(self.EXPECTED_INDEXES)
        added = actual - documented
        self.assertEqual(
            added, set(),
            f"SCHEMA has {len(added)} "
            f"undocumented index(es): "
            f"{sorted(added)}. If an "
            f"index was intentionally "
            f"added, update "
            f"EXPECTED_INDEXES in the "
            f"same commit."
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
