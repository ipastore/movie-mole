"""Keep the AuraDB Free instance from auto-pausing.

Free instances pause after 72 hours of inactivity, do not auto-resume, and are deleted
after 30 days paused. A paused instance does not serve, so nothing client-side can wake
it -- prevention is the only mechanism.

This performs a WRITE, not a read: a write is unambiguously activity, whereas whether a
read resets Aura's inactivity timer is not documented. It touches the readiness node the
loader already creates, so it adds no nodes and cannot disturb the ownership assertion or
the expected-count verification.

    python -m ingestion.keepalive

Schedule it well inside the 72h window -- daily, not every other day, so one missed run
is survivable. In Phase 4 this moves to a Cloudflare Cron Trigger; until then, cron:

    0 4 * * *  cd /path/to/movie_mole && .venv/bin/python -m ingestion.keepalive >> /tmp/mm-keepalive.log 2>&1
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from ingestion.load import LOCK_KEY, load_dotenv

PING_QUERY = """
MERGE (x:Meta {key: $key})
ON CREATE SET x.ready = false
SET x.lastPingAt = datetime()
RETURN x.lastPingAt AS lastPingAt, coalesce(x.ready, false) AS ready
"""


def main() -> int:
    load_dotenv(Path(__file__).with_name(".env"))
    uri = os.environ.get("NEO4J_URI")
    username = os.environ.get("NEO4J_USERNAME")
    password = os.environ.get("NEO4J_PASSWORD")
    if not all((uri, username, password)):
        print("NEO4J_URI, NEO4J_USERNAME, and NEO4J_PASSWORD are required", file=sys.stderr)
        return 2

    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(uri, auth=(username, password))
    try:
        driver.verify_connectivity()
        with driver.session() as session:
            record = session.run(PING_QUERY, key=LOCK_KEY).single()
    finally:
        driver.close()

    if record is None:
        print("ping returned no record", file=sys.stderr)
        return 1

    print(f"pinged at {record['lastPingAt']}  (graph ready: {record['ready']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
