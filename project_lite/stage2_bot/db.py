from __future__ import annotations

import importlib
import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class DatabaseError(Exception):
    """Raised on DB adapter and query errors."""


@dataclass
class UserRecord:
    id: int
    telegram_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    birth_date: str | None
    gender: str | None
    bio: str | None
    city: str | None
    profile_completeness: float
    status: str
    photo_count: int
    created_at: str
    updated_at: str


@dataclass
class PreferenceRecord:
    age_min: int
    age_max: int
    preferred_gender: str
    preferred_city: str
    max_distance_km: int | None


@dataclass
class PhotoRecord:
    id: int
    telegram_file_id: str
    telegram_file_unique_id: str
    position: int
    is_primary: bool


@dataclass
class CandidateStats:
    user: UserRecord
    likes_received: int
    skips_received: int
    matches_count: int


@dataclass
class ActionResult:
    action_type: str
    target: UserRecord
    is_match: bool


class PostgresRepository:
    """PostgreSQL data layer for registration, profiles and matching."""

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
        insert into users (
            telegram_id,
            username,
            first_name,
            last_name
        )
        values (%s, %s, %s, %s)
        on conflict (telegram_id)
        do update set
            username = excluded.username,
            first_name = excluded.first_name,
            last_name = excluded.last_name,
            status = 'active',
            updated_at = now()
        returning id;
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (telegram_id, username, first_name, last_name))
                row = cur.fetchone()
            conn.commit()
        return self.get_user_by_id(int(row[0]))

    def get_user_by_telegram_id(self, telegram_id: int) -> UserRecord | None:
        return self._fetch_user("u.telegram_id = %s", (telegram_id,))

    def get_user_by_id(self, user_id: int) -> UserRecord:
        user = self._fetch_user("u.id = %s", (user_id,))
        if user is None:
            raise DatabaseError(f"user with id={user_id} does not exist")
        return user

    def count_users(self) -> int:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("select count(*) from users;")
                row = cur.fetchone()
        return int(row[0])

    def update_profile(
        self,
        telegram_id: int,
        birth_date: str | None = None,
        gender: str | None = None,
        city: str | None = None,
        bio: str | None = None,
    ) -> UserRecord:
        user = self.get_user_by_telegram_id(telegram_id)
        if user is None:
            raise DatabaseError("profile does not exist. Send /start first")

        query = """
        update users
        set
            birth_date = coalesce(%s::date, birth_date),
            gender = coalesce(%s, gender),
            city = coalesce(%s, city),
            bio = coalesce(%s, bio),
            status = 'active',
            updated_at = now()
        where telegram_id = %s
        returning id;
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (birth_date, gender, city, bio, telegram_id))
                row = cur.fetchone()
            conn.commit()

        user_id = int(row[0])
        self.recalculate_profile_completeness(user_id)
        return self.get_user_by_id(user_id)

    def delete_profile(self, telegram_id: int) -> bool:
        query = "delete from users where telegram_id = %s returning id;"
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (telegram_id,))
                row = cur.fetchone()
            conn.commit()
        return row is not None

    def ensure_default_preferences(self, telegram_id: int) -> PreferenceRecord:
        user = self.get_user_by_telegram_id(telegram_id)
        if user is None:
            raise DatabaseError(f"user with telegram_id={telegram_id} is not registered")

        with self._connect() as conn:
            with conn.cursor() as cur:
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
                    do update set updated_at = user_preferences.updated_at
                    returning age_min, age_max, preferred_gender, preferred_city, max_distance_km;
                    """,
                    (user.id,),
                )
                pref_row = cur.fetchone()
            conn.commit()
        return self._row_to_preference(pref_row)

    def update_preferences(
        self,
        telegram_id: int,
        age_min: int | None = None,
        age_max: int | None = None,
        preferred_gender: str | None = None,
        preferred_city: str | None = None,
        max_distance_km: int | None = None,
    ) -> PreferenceRecord:
        user = self.get_user_by_telegram_id(telegram_id)
        if user is None:
            raise DatabaseError("preferences cannot be updated before /start")
        self.ensure_default_preferences(telegram_id)

        query = """
        update user_preferences
        set
            age_min = coalesce(%s, age_min),
            age_max = coalesce(%s, age_max),
            preferred_gender = coalesce(%s, preferred_gender),
            preferred_city = coalesce(%s, preferred_city),
            max_distance_km = coalesce(%s, max_distance_km),
            updated_at = now()
        where user_id = %s
        returning age_min, age_max, preferred_gender, preferred_city, max_distance_km;
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    query,
                    (
                        age_min,
                        age_max,
                        preferred_gender,
                        preferred_city,
                        max_distance_km,
                        user.id,
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        return self._row_to_preference(row)

    def add_photo(
        self,
        telegram_id: int,
        telegram_file_id: str,
        telegram_file_unique_id: str,
        position: int | None = None,
        is_primary: bool = False,
    ) -> PhotoRecord:
        user = self.get_user_by_telegram_id(telegram_id)
        if user is None:
            raise DatabaseError("photo cannot be added before /start")
        next_position = position or min(user.photo_count + 1, 10)

        query = """
        insert into user_photos (
            user_id,
            telegram_file_id,
            telegram_file_unique_id,
            position,
            is_primary
        )
        values (%s, %s, %s, %s, %s)
        on conflict (telegram_file_unique_id)
        do update set
            telegram_file_id = excluded.telegram_file_id,
            position = excluded.position,
            is_primary = excluded.is_primary,
            is_active = true
        returning id, telegram_file_id, telegram_file_unique_id, position, is_primary;
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    query,
                    (
                        user.id,
                        telegram_file_id,
                        telegram_file_unique_id,
                        next_position,
                        is_primary or user.photo_count == 0,
                    ),
                )
                row = cur.fetchone()
            conn.commit()

        self.recalculate_profile_completeness(user.id)
        return PhotoRecord(
            id=int(row[0]),
            telegram_file_id=str(row[1]),
            telegram_file_unique_id=str(row[2]),
            position=int(row[3]),
            is_primary=bool(row[4]),
        )

    def get_primary_photo(self, user_id: int) -> PhotoRecord | None:
        query = """
        select
            id,
            telegram_file_id,
            telegram_file_unique_id,
            position,
            is_primary
        from user_photos
        where user_id = %s
          and is_active = true
        order by is_primary desc, position asc, id asc
        limit 1;
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (user_id,))
                row = cur.fetchone()
        if row is None:
            return None
        return PhotoRecord(
            id=int(row[0]),
            telegram_file_id=str(row[1]),
            telegram_file_unique_id=str(row[2]),
            position=int(row[3]),
            is_primary=bool(row[4]),
        )

    def list_photos(self, user_id: int, limit: int = 10) -> list[PhotoRecord]:
        query = """
        select
            id,
            telegram_file_id,
            telegram_file_unique_id,
            position,
            is_primary
        from user_photos
        where user_id = %s
          and is_active = true
        order by is_primary desc, position asc, id asc
        limit %s;
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (user_id, limit))
                rows = cur.fetchall()
        return [
            PhotoRecord(
                id=int(row[0]),
                telegram_file_id=str(row[1]),
                telegram_file_unique_id=str(row[2]),
                position=int(row[3]),
                is_primary=bool(row[4]),
            )
            for row in rows
        ]

    def list_candidates_for_user(self, viewer_user_id: int, limit: int = 200) -> list[CandidateStats]:
        query = f"""
        select
            {self._user_select_columns("u")},
            coalesce((
                select count(*)
                from user_actions a
                where a.target_user_id = u.id and a.action_type = 'like'
            ), 0) as likes_received,
            coalesce((
                select count(*)
                from user_actions a
                where a.target_user_id = u.id and a.action_type = 'skip'
            ), 0) as skips_received,
            coalesce((
                select count(*)
                from matches m
                where m.user_a_id = u.id or m.user_b_id = u.id
            ), 0) as matches_count
        from users u
        where u.id <> %s
          and u.status = 'active'
          and not exists (
              select 1
              from user_actions a
              where a.actor_user_id = %s and a.target_user_id = u.id
          )
          and not exists (
              select 1
              from matches m
              where (m.user_a_id = %s and m.user_b_id = u.id)
                 or (m.user_b_id = %s and m.user_a_id = u.id)
          )
        order by u.updated_at desc
        limit %s;
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (viewer_user_id, viewer_user_id, viewer_user_id, viewer_user_id, limit))
                rows = cur.fetchall()

        stats: list[CandidateStats] = []
        user_columns_count = self._user_column_count()
        for row in rows:
            user = self._row_to_user(row[:user_columns_count])
            stats.append(
                CandidateStats(
                    user=user,
                    likes_received=int(row[user_columns_count]),
                    skips_received=int(row[user_columns_count + 1]),
                    matches_count=int(row[user_columns_count + 2]),
                )
            )
        return stats

    def record_action(self, actor_telegram_id: int, target_user_id: int, action_type: str) -> ActionResult:
        if action_type not in {"like", "skip", "block"}:
            raise DatabaseError(f"unsupported action type: {action_type}")

        actor = self.get_user_by_telegram_id(actor_telegram_id)
        if actor is None:
            raise DatabaseError("action cannot be recorded before /start")
        target = self.get_user_by_id(target_user_id)

        query = """
        insert into user_actions (actor_user_id, target_user_id, action_type)
        values (%s, %s, %s)
        on conflict (actor_user_id, target_user_id)
        do update set action_type = excluded.action_type, updated_at = now();
        """
        is_match = False
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (actor.id, target_user_id, action_type))
                if action_type == "like":
                    cur.execute(
                        """
                        select 1
                        from user_actions
                        where actor_user_id = %s
                          and target_user_id = %s
                          and action_type = 'like';
                        """,
                        (target_user_id, actor.id),
                    )
                    if cur.fetchone() is not None:
                        first_user_id = min(actor.id, target_user_id)
                        second_user_id = max(actor.id, target_user_id)
                        cur.execute(
                            """
                            insert into matches (user_a_id, user_b_id)
                            values (%s, %s)
                            on conflict do nothing
                            returning id;
                            """,
                            (first_user_id, second_user_id),
                        )
                        is_match = True
            conn.commit()

        return ActionResult(action_type=action_type, target=target, is_match=is_match)

    def recalculate_profile_completeness(self, user_id: int) -> float:
        query = """
        with profile as (
            select
                u.id,
                (
                    case when u.birth_date is not null then 1 else 0 end +
                    case when u.gender is not null then 1 else 0 end +
                    case when nullif(trim(coalesce(u.city, '')), '') is not null then 1 else 0 end +
                    case when nullif(trim(coalesce(u.bio, '')), '') is not null then 1 else 0 end +
                    case when exists (
                        select 1
                        from user_photos p
                        where p.user_id = u.id and p.is_active
                    ) then 1 else 0 end
                ) * 20.0 as completeness
            from users u
            where u.id = %s
        )
        update users u
        set profile_completeness = profile.completeness,
            updated_at = now()
        from profile
        where u.id = profile.id
        returning u.profile_completeness;
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (user_id,))
                row = cur.fetchone()
            conn.commit()
        return float(row[0])

    def _fetch_user(self, where_sql: str, params: tuple[Any, ...]) -> UserRecord | None:
        query = f"""
        select {self._user_select_columns("u")}
        from users u
        where {where_sql};
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                row = cur.fetchone()
        if row is None:
            return None
        return self._row_to_user(row)

    def _connect(self) -> Any:
        try:
            return self._psycopg.connect(self.database_url)
        except Exception as exc:
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
    def _row_to_preference(row: Any) -> PreferenceRecord:
        return PreferenceRecord(
            age_min=int(row[0]),
            age_max=int(row[1]),
            preferred_gender=str(row[2]),
            preferred_city=str(row[3]),
            max_distance_km=None if row[4] is None else int(row[4]),
        )

    @staticmethod
    def _user_select_columns(alias: str) -> str:
        return f"""
            {alias}.id,
            {alias}.telegram_id,
            {alias}.username,
            {alias}.first_name,
            {alias}.last_name,
            {alias}.birth_date,
            {alias}.gender,
            {alias}.bio,
            {alias}.city,
            {alias}.profile_completeness,
            {alias}.status,
            (
                select count(*)
                from user_photos p
                where p.user_id = {alias}.id and p.is_active
            ) as photo_count,
            {alias}.created_at,
            {alias}.updated_at
        """

    @staticmethod
    def _user_column_count() -> int:
        return 14

    @staticmethod
    def _row_to_user(row: Any) -> UserRecord:
        return UserRecord(
            id=int(row[0]),
            telegram_id=int(row[1]),
            username=row[2],
            first_name=row[3],
            last_name=row[4],
            birth_date=None if row[5] is None else str(row[5]),
            gender=row[6],
            bio=row[7],
            city=row[8],
            profile_completeness=float(row[9]),
            status=str(row[10]),
            photo_count=int(row[11]),
            created_at=str(row[12]),
            updated_at=str(row[13]),
        )
