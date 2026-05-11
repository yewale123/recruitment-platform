"""
init_db.py — Idempotent database initializer for the Recruitment Platform.

Usage:
    python init_db.py

Behavior:
  - Reads all configuration from .env (copy .env.example → .env and fill in your values)
  - Connects to MySQL and creates the database if it does not exist
  - For each table: checks whether it exists and creates it only if missing
  - Safe to run multiple times — never drops or alters existing tables
"""

import sys
import os
import pymysql
from dotenv import load_dotenv

load_dotenv()

# ── Configuration from .env ───────────────────────────────────────────────────

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "recruitment_platform")


# ── Table DDL definitions ─────────────────────────────────────────────────────

TABLES = {
    "recruitment_requests": """
        CREATE TABLE recruitment_requests (
            id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            title           VARCHAR(255) NOT NULL,
            required_skills JSON         NOT NULL,
            experience_min  TINYINT UNSIGNED NOT NULL DEFAULT 0,
            experience_max  TINYINT UNSIGNED NULL,
            location        VARCHAR(255) NULL,
            keywords        JSON         NOT NULL DEFAULT (JSON_ARRAY()),
            platforms       JSON         NOT NULL,
            status          ENUM('pending', 'running', 'completed', 'failed')
                            NOT NULL DEFAULT 'pending',
            created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                            ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    "scrape_jobs": """
        CREATE TABLE scrape_jobs (
            id               INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            request_id       INT UNSIGNED NOT NULL,
            platform         VARCHAR(50)  NOT NULL,
            celery_task_id   VARCHAR(255) NULL,
            status           ENUM('pending', 'running', 'completed', 'failed')
                             NOT NULL DEFAULT 'pending',
            error_message    TEXT         NULL,
            candidates_found INT UNSIGNED NOT NULL DEFAULT 0,
            started_at       DATETIME     NULL,
            completed_at     DATETIME     NULL,

            CONSTRAINT fk_scrape_jobs_request
                FOREIGN KEY (request_id)
                REFERENCES recruitment_requests(id)
                ON DELETE CASCADE,

            INDEX idx_scrape_jobs_request (request_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    "candidates": """
        CREATE TABLE candidates (
            id                INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            request_id        INT UNSIGNED     NOT NULL,
            scrape_job_id     INT UNSIGNED     NOT NULL,
            platform          VARCHAR(50)      NOT NULL,
            platform_id       VARCHAR(255)     NOT NULL,
            full_name         VARCHAR(255)     NULL,
            headline          VARCHAR(500)     NULL,
            location          VARCHAR(255)     NULL,
            experience_years  DECIMAL(4,1)     NULL,
            skills            JSON             NOT NULL DEFAULT (JSON_ARRAY()),
            profile_url       VARCHAR(1000)    NULL,
            summary           TEXT             NULL,
            suitability_score DECIMAL(5,2)     NULL,
            score_breakdown   JSON             NULL,
            `rank`            INT UNSIGNED     NULL,
            raw_data          JSON             NULL,
            created_at        DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,

            CONSTRAINT fk_candidates_request
                FOREIGN KEY (request_id)
                REFERENCES recruitment_requests(id)
                ON DELETE CASCADE,

            CONSTRAINT fk_candidates_scrape_job
                FOREIGN KEY (scrape_job_id)
                REFERENCES scrape_jobs(id)
                ON DELETE CASCADE,

            -- Prevents scraping the same profile twice for the same request
            UNIQUE INDEX idx_candidates_dedup (request_id, platform, platform_id),

            -- Fast sorted fetch of ranked candidates for a request
            INDEX idx_candidates_request_rank (request_id, `rank`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
}

# Tables must be created in this order due to foreign key dependencies
TABLE_ORDER = ["recruitment_requests", "scrape_jobs", "candidates"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_connection(database: str | None = None) -> pymysql.Connection:
    """Return a pymysql connection. Pass database=None to connect without selecting a DB."""
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=database,
        charset="utf8mb4",
        autocommit=True,
    )


def ensure_database(conn: pymysql.Connection) -> None:
    """Create the database if it does not already exist."""
    with conn.cursor() as cur:
        cur.execute(
            f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` "
            f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
    print(f"  [db]  Database '{DB_NAME}' is ready.")


def table_exists(conn: pymysql.Connection, table_name: str) -> bool:
    """Check information_schema to see if a table exists in the target database."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = %s
              AND table_name   = %s
            """,
            (DB_NAME, table_name),
        )
        (count,) = cur.fetchone()
        return count > 0


def create_table(conn: pymysql.Connection, table_name: str, ddl: str) -> None:
    """Execute a CREATE TABLE statement."""
    with conn.cursor() as cur:
        cur.execute(ddl)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\n=== Recruitment Platform — DB Initializer ===\n")
    print(f"  Host : {DB_HOST}:{DB_PORT}")
    print(f"  User : {DB_USER}")
    print(f"  DB   : {DB_NAME}\n")

    # Step 1: connect without a database selected, create DB if needed
    try:
        root_conn = get_connection(database=None)
    except pymysql.OperationalError as e:
        print(f"[ERROR] Could not connect to MySQL: {e}")
        print("  → Check DB_HOST, DB_PORT, DB_USER, DB_PASSWORD in your .env file.")
        sys.exit(1)

    try:
        ensure_database(root_conn)
    finally:
        root_conn.close()

    # Step 2: connect to the target database and create missing tables
    try:
        conn = get_connection(database=DB_NAME)
    except pymysql.OperationalError as e:
        print(f"[ERROR] Could not connect to database '{DB_NAME}': {e}")
        sys.exit(1)

    created = []
    skipped = []

    try:
        for table_name in TABLE_ORDER:
            ddl = TABLES[table_name]
            if table_exists(conn, table_name):
                skipped.append(table_name)
                print(f"  [ok]  Table '{table_name}' already exists — skipped.")
            else:
                try:
                    create_table(conn, table_name, ddl)
                    created.append(table_name)
                    print(f"  [+]   Table '{table_name}' created.")
                except pymysql.Error as e:
                    print(f"  [ERROR] Failed to create table '{table_name}': {e}")
                    sys.exit(1)
    finally:
        conn.close()

    # Summary
    print()
    if created:
        print(f"Done. Created {len(created)} table(s): {', '.join(created)}")
    else:
        print("Done. All tables were already present — nothing to do.")
    print()


if __name__ == "__main__":
    main()
