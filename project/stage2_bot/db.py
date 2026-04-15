from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class DatabaseError(Exception):
    """Raised on DB adapter and query errors."""


@dataclass
class UserRecord:
    telegram_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    birth_date: str | None
    gender: str | None
    city: str | None
    profile_completeness: float
    created_at: str
    updated_at: str


@dataclass
class PreferenceRecord:
    age_min: int
    age_max: int
    preferred_gender: str
    preferred_city: str
    max_distance_km: int | None


class PostgresRepository:
    """Data layer (PostgreSQL) from Stage 1 docs."""

    def __init__(self, database_url: str, schema_path: str = "db/schema.sql") -> None:
        self.database_url = database_url
        self.schema_path = schema_path
        self._psycopg = self._load_psycopg()

    def initialize(self) -> None:
        sql = Path(self.schema_path).read_text(encoding="utf-8")
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()

    def register_or_update_user(
        self,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
    ) -> UserRecord:
        query = """
        insert into users (telegram_id, username, first_name, last_name)
        values (%s, %s, %s, %s)
        on conflict (telegram_id)
        do update set
            username = excluded.username,
            first_name = excluded.first_name,
            last_name = excluded.last_name,
            updated_at = now()
        returning
            telegram_id,
            username,
            first_name,
            last_name,
            birth_date,
            gender,
            city,
            profile_completeness,
            created_at,
            updated_at;
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (telegram_id, username, first_name, last_name))
                row = cur.fetchone()
            conn.commit()
        return self._row_to_user(row)

    def get_user_by_telegram_id(self, telegram_id: int) -> UserRecord | None:
        query = """
        select
            telegram_id,
            username,
            first_name,
            last_name,
            birth_date,
            gender,
            city,
            profile_completeness,
            created_at,
            updated_at
        from users
        where telegram_id = %s;
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (telegram_id,))
                row = cur.fetchone()
        if row is None:
            return None
        return self._row_to_user(row)

    def count_users(self) -> int:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("select count(*) from users;")
                row = cur.fetchone()
        return int(row[0])

    def ensure_default_preferences(self, telegram_id: int) -> PreferenceRecord:
        user_id_query = "select id from users where telegram_id = %s;"
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(user_id_query, (telegram_id,))
                row = cur.fetchone()
                if row is None:
                    raise DatabaseError(f"user with telegram_id={telegram_id} is not registered")
                user_id = int(row[0])

                cur.execute(
                    """
                    insert into user_preferences (
                        user_id,
                        age_min,
                        age_max,
                        preferred_gender,
                        preferred_city,
                        max_distance_km
                    )
                    values (%s, 18, 35, 'any', 'any', 50)
                    on conflict (user_id)
                    do update set
                        updated_at = now()
                    returning age_min, age_max, preferred_gender, preferred_city, max_distance_km;
                    """,
                    (user_id,),
                )
                pref_row = cur.fetchone()
            conn.commit()
        return PreferenceRecord(
            age_min=int(pref_row[0]),
            age_max=int(pref_row[1]),
            preferred_gender=str(pref_row[2]),
            preferred_city=str(pref_row[3]),
            max_distance_km=None if pref_row[4] is None else int(pref_row[4]),
        )

    def _connect(self) -> Any:
        try:
            return self._psycopg.connect(self.database_url)
        except Exception as exc:  # pragma: no cover - depends on environment
            raise DatabaseError(f"failed to connect to postgres: {exc}") from exc

    @staticmethod
    def _load_psycopg() -> Any:
        module = importlib.util.find_spec("psycopg")
        if module is None:
            raise DatabaseError(
                "python package 'psycopg' is not installed. "
                "Install it with: pip install psycopg[binary]"
            )
        return importlib.import_module("psycopg")

    @staticmethod
    def _row_to_user(row: Any) -> UserRecord:
        return UserRecord(
            telegram_id=int(row[0]),
            username=row[1],
            first_name=row[2],
            last_name=row[3],
            birth_date=None if row[4] is None else str(row[4]),
            gender=row[5],
            city=row[6],
            profile_completeness=float(row[7]),
            created_at=str(row[8]),
            updated_at=str(row[9]),
        )

