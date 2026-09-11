"""LanceDB helpers shared by the ingestion and retrieval adapters.

Why this module exists
----------------------
LanceDB 0.38 changed ``connect(...).list_tables()`` to return a
``ListTablesResponse`` — a paged object carrying ``context``, ``tables`` and
``page_token`` — where it used to return a plain list of table names.

Both adapters had been written against the old shape and tested membership
directly::

    if self._table_name not in db.list_tables():   # always False

Membership against a ``ListTablesResponse`` compares the name to the object's
*attributes* (``context``, ``tables``, ``page_token``), never to the table
names, so the check silently answered "no table" even when the table existed
and held rows. The visible symptoms were:

* ``POST /api/documents/{id}/reindex`` returned ``chunk_count: 0`` for a
  document that had just been indexed successfully ("Indexed 1 vectors"),
* ``DELETE`` reported zero rows purged,
* retrieval's ``has_table()`` reported "nothing indexed", so search claimed
  the corpus was empty after a successful ingest.

None of these raised: the wrong answer was indistinguishable from an empty
index, which is why it survived. The helpers below normalise the response so
callers ask a question with one meaning across LanceDB versions.
"""

from __future__ import annotations

from typing import Any


def table_names(db: Any) -> set[str]:
    """Names of every table in an open LanceDB database.

    Reads ``ListTablesResponse.tables`` on modern LanceDB and falls back to
    the deprecated ``table_names()`` for older builds.
    """
    response = db.list_tables()
    names = getattr(response, "tables", None)
    if names is None:
        # Pre-0.38 LanceDB: returns a plain list, or exposes table_names().
        if isinstance(response, (list, tuple, set)):
            return {str(name) for name in response}
        names = db.table_names()  # pragma: no cover - legacy builds only
    return {str(name) for name in names}


def has_table(db: Any, name: str) -> bool:
    """Whether ``name`` exists in an open LanceDB database."""
    return name in table_names(db)
