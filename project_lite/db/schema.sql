create table if not exists users (
    id bigserial primary key,
    telegram_id bigint not null unique,
    username text,
    first_name text,
    last_name text,
    birth_date date,
    gender text check (gender in ('male', 'female', 'other')),
    bio text,
    city text,
    latitude numeric(9,6),
    longitude numeric(9,6),
    profile_completeness numeric(5,2) not null default 0
        check (profile_completeness between 0 and 100),
    status text not null default 'active'
        check (status in ('active', 'paused', 'banned')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table users add column if not exists telegram_id bigint;
alter table users add column if not exists username text;
alter table users add column if not exists first_name text;
alter table users add column if not exists last_name text;
alter table users add column if not exists birth_date date;
alter table users add column if not exists gender text;
alter table users add column if not exists bio text;
alter table users add column if not exists city text;
alter table users add column if not exists latitude numeric(9,6);
alter table users add column if not exists longitude numeric(9,6);
alter table users add column if not exists profile_completeness numeric(5,2) not null default 0;
alter table users add column if not exists status text not null default 'active';
alter table users add column if not exists created_at timestamptz not null default now();
alter table users add column if not exists updated_at timestamptz not null default now();
alter table users alter column birth_date drop not null;
alter table users alter column gender drop not null;
alter table users alter column city drop not null;
alter table users drop column if exists referred_by_user_id;
alter table users drop column if exists referral_code;

create unique index if not exists uq_users_telegram_id on users(telegram_id);
drop index if exists uq_users_referral_code;
create index if not exists idx_users_status on users(status);
create index if not exists idx_users_status_updated_at on users(status, updated_at desc);
create index if not exists idx_users_city_gender on users(city, gender);

create table if not exists user_photos (
    id bigserial primary key,
    user_id bigint not null references users(id) on delete cascade,
    telegram_file_id text not null,
    telegram_file_unique_id text not null unique,
    position smallint not null default 1 check (position between 1 and 10),
    is_primary boolean not null default false,
    is_active boolean not null default true,
    created_at timestamptz not null default now()
);

create index if not exists idx_user_photos_user_id on user_photos(user_id);
create index if not exists idx_user_photos_active_lookup
on user_photos(user_id, is_active, is_primary desc, position asc);

create table if not exists user_preferences (
    user_id bigint primary key references users(id) on delete cascade,
    age_min smallint not null check (age_min between 18 and 99),
    age_max smallint not null check (age_max between 18 and 99 and age_max >= age_min),
    preferred_gender text not null check (preferred_gender in ('male', 'female', 'any')),
    preferred_city text not null,
    max_distance_km int check (max_distance_km between 1 and 500),
    updated_at timestamptz not null default now()
);

create table if not exists user_actions (
    actor_user_id bigint not null references users(id) on delete cascade,
    target_user_id bigint not null references users(id) on delete cascade,
    action_type text not null check (action_type in ('like', 'skip', 'block')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key (actor_user_id, target_user_id),
    check (actor_user_id <> target_user_id)
);

alter table user_actions add column if not exists updated_at timestamptz not null default now();

create index if not exists idx_user_actions_actor on user_actions(actor_user_id);
create index if not exists idx_user_actions_target on user_actions(target_user_id);
create index if not exists idx_user_actions_target_type on user_actions(target_user_id, action_type);

create table if not exists matches (
    id bigserial primary key,
    user_a_id bigint not null references users(id) on delete cascade,
    user_b_id bigint not null references users(id) on delete cascade,
    created_at timestamptz not null default now(),
    check (user_a_id <> user_b_id)
);

create unique index if not exists uq_matches_pair
on matches (least(user_a_id, user_b_id), greatest(user_a_id, user_b_id));

create index if not exists idx_matches_user_a on matches(user_a_id);
create index if not exists idx_matches_user_b on matches(user_b_id);
