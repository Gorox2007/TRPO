-- Test data for quick Stage 3 manual checks.
-- Safe to run multiple times.

with seed_users(telegram_id, username, first_name, last_name, birth_date, gender, city, bio, profile_completeness) as (
    values
        (900001, 'seed_alina', 'Алина', 'Смирнова', date '1999-05-12', 'female', 'Москва', 'Люблю джаз, выставки и ночные прогулки.', 82.00),
        (900002, 'seed_masha', 'Маша', 'Волкова', date '1998-02-17', 'female', 'Москва', 'Пеку чизкейки и бегаю по утрам.', 88.00),
        (900003, 'seed_liza', 'Лиза', 'Котова', date '2001-08-24', 'female', 'Санкт-Петербург', 'Архитектура, кофе и спонтанные поездки.', 79.00),
        (900004, 'seed_olga', 'Ольга', 'Егорова', date '1997-11-03', 'female', 'Казань', 'Йога, книги и сериалы в оригинале.', 84.00),
        (900005, 'seed_nastya', 'Настя', 'Морозова', date '2000-06-29', 'female', 'Москва', 'Сапы, концерты и late night chats.', 91.00),
        (900006, 'seed_ira', 'Ира', 'Федорова', date '1996-09-14', 'female', 'Новосибирск', 'Катаюсь на сноуборде и люблю мемы.', 77.00),
        (900007, 'seed_ivan', 'Иван', 'Петров', date '1997-03-18', 'male', 'Москва', 'Стартапы, настолки и хороший фильтр-кофе.', 86.00),
        (900008, 'seed_dima', 'Дима', 'Соколов', date '1995-12-08', 'male', 'Москва', 'Горы, бег и разговоры до утра.', 83.00),
        (900009, 'seed_artyom', 'Артём', 'Лебедев', date '2000-01-27', 'male', 'Санкт-Петербург', 'Фотографирую город и ищу компанию в Эрмитаж.', 80.00),
        (900010, 'seed_kirill', 'Кирилл', 'Попов', date '1998-07-15', 'male', 'Екатеринбург', 'Гитара, крафтовые лимонады и поездки на выходных.', 78.00),
        (900011, 'seed_max', 'Макс', 'Кузнецов', date '1996-04-09', 'male', 'Казань', 'Люблю готовить пасту и смотреть футбол.', 76.00),
        (900012, 'seed_nikita', 'Никита', 'Орлов', date '2001-10-30', 'male', 'Москва', 'Прогулки по центру, музеи и короткие путешествия.', 89.00)
)
insert into users (
    telegram_id,
    username,
    first_name,
    last_name,
    birth_date,
    gender,
    city,
    bio,
    profile_completeness,
    status
)
select
    telegram_id,
    username,
    first_name,
    last_name,
    birth_date,
    gender,
    city,
    bio,
    profile_completeness,
    'active'
from seed_users
on conflict (telegram_id)
do update set
    username = excluded.username,
    first_name = excluded.first_name,
    last_name = excluded.last_name,
    birth_date = excluded.birth_date,
    gender = excluded.gender,
    city = excluded.city,
    bio = excluded.bio,
    profile_completeness = excluded.profile_completeness,
    status = 'active',
    updated_at = now();

with pref_seed(telegram_id, age_min, age_max, preferred_gender, preferred_city, max_distance_km) as (
    values
        (900001, 24, 34, 'male', 'Москва', 50),
        (900002, 23, 33, 'male', 'Москва', 30),
        (900003, 24, 36, 'male', 'Санкт-Петербург', 40),
        (900004, 25, 35, 'male', 'any', 100),
        (900005, 22, 31, 'male', 'Москва', 25),
        (900006, 24, 37, 'male', 'any', 200),
        (900007, 21, 32, 'female', 'Москва', 50),
        (900008, 24, 34, 'female', 'Москва', 50),
        (900009, 22, 31, 'female', 'Санкт-Петербург', 35),
        (900010, 22, 35, 'female', 'any', 150),
        (900011, 23, 34, 'female', 'Казань', 50),
        (900012, 20, 30, 'female', 'Москва', 30)
)
insert into user_preferences (user_id, age_min, age_max, preferred_gender, preferred_city, max_distance_km)
select
    u.id,
    p.age_min,
    p.age_max,
    p.preferred_gender,
    p.preferred_city,
    p.max_distance_km
from pref_seed p
join users u on u.telegram_id = p.telegram_id
on conflict (user_id)
do update set
    age_min = excluded.age_min,
    age_max = excluded.age_max,
    preferred_gender = excluded.preferred_gender,
    preferred_city = excluded.preferred_city,
    max_distance_km = excluded.max_distance_km,
    updated_at = now();

with photo_seed(telegram_id, telegram_file_id, telegram_file_unique_id, position, is_primary) as (
    values
        (900001, 'https://randomuser.me/api/portraits/women/44.jpg', 'seed-photo-900001', 1, true),
        (900001, 'https://randomuser.me/api/portraits/women/45.jpg', 'seed-photo-900001-b', 2, false),
        (900002, 'https://randomuser.me/api/portraits/women/68.jpg', 'seed-photo-900002', 1, true),
        (900002, 'https://randomuser.me/api/portraits/women/69.jpg', 'seed-photo-900002-b', 2, false),
        (900003, 'https://randomuser.me/api/portraits/women/33.jpg', 'seed-photo-900003', 1, true),
        (900003, 'https://randomuser.me/api/portraits/women/34.jpg', 'seed-photo-900003-b', 2, false),
        (900004, 'https://randomuser.me/api/portraits/women/21.jpg', 'seed-photo-900004', 1, true),
        (900004, 'https://randomuser.me/api/portraits/women/22.jpg', 'seed-photo-900004-b', 2, false),
        (900005, 'https://randomuser.me/api/portraits/women/56.jpg', 'seed-photo-900005', 1, true),
        (900005, 'https://randomuser.me/api/portraits/women/57.jpg', 'seed-photo-900005-b', 2, false),
        (900006, 'https://randomuser.me/api/portraits/women/74.jpg', 'seed-photo-900006', 1, true),
        (900006, 'https://randomuser.me/api/portraits/women/75.jpg', 'seed-photo-900006-b', 2, false),
        (900007, 'https://randomuser.me/api/portraits/men/32.jpg', 'seed-photo-900007', 1, true),
        (900007, 'https://randomuser.me/api/portraits/men/33.jpg', 'seed-photo-900007-b', 2, false),
        (900008, 'https://randomuser.me/api/portraits/men/41.jpg', 'seed-photo-900008', 1, true),
        (900008, 'https://randomuser.me/api/portraits/men/42.jpg', 'seed-photo-900008-b', 2, false),
        (900009, 'https://randomuser.me/api/portraits/men/53.jpg', 'seed-photo-900009', 1, true),
        (900009, 'https://randomuser.me/api/portraits/men/54.jpg', 'seed-photo-900009-b', 2, false),
        (900010, 'https://randomuser.me/api/portraits/men/62.jpg', 'seed-photo-900010', 1, true),
        (900010, 'https://randomuser.me/api/portraits/men/63.jpg', 'seed-photo-900010-b', 2, false),
        (900011, 'https://randomuser.me/api/portraits/men/75.jpg', 'seed-photo-900011', 1, true),
        (900011, 'https://randomuser.me/api/portraits/men/76.jpg', 'seed-photo-900011-b', 2, false),
        (900012, 'https://randomuser.me/api/portraits/men/86.jpg', 'seed-photo-900012', 1, true),
        (900012, 'https://randomuser.me/api/portraits/men/87.jpg', 'seed-photo-900012-b', 2, false)
)
insert into user_photos (user_id, telegram_file_id, telegram_file_unique_id, position, is_primary, is_active)
select
    u.id,
    p.telegram_file_id,
    p.telegram_file_unique_id,
    p.position,
    p.is_primary,
    true
from photo_seed p
join users u on u.telegram_id = p.telegram_id
on conflict (telegram_file_unique_id)
do update set
    telegram_file_id = excluded.telegram_file_id,
    position = excluded.position,
    is_primary = excluded.is_primary,
    is_active = true;

with action_seed(actor_telegram_id, target_telegram_id, action_type) as (
    values
        (900007, 900001, 'like'),
        (900001, 900007, 'like'),
        (900008, 900002, 'like'),
        (900002, 900008, 'like'),
        (900012, 900005, 'like'),
        (900005, 900012, 'skip'),
        (900011, 900004, 'like'),
        (900004, 900011, 'like'),
        (900009, 900003, 'like'),
        (900003, 900009, 'like'),
        (900010, 900006, 'skip'),
        (900006, 900010, 'like'),
        (900007, 900005, 'like'),
        (900008, 900005, 'skip'),
        (900012, 900001, 'like')
)
insert into user_actions (actor_user_id, target_user_id, action_type)
select
    actor.id,
    target.id,
    a.action_type
from action_seed a
join users actor on actor.telegram_id = a.actor_telegram_id
join users target on target.telegram_id = a.target_telegram_id
on conflict (actor_user_id, target_user_id)
do update set
    action_type = excluded.action_type,
    updated_at = now();

with match_seed(user_a_telegram_id, user_b_telegram_id) as (
    values
        (900001, 900007),
        (900002, 900008),
        (900003, 900009),
        (900004, 900011)
)
insert into matches (user_a_id, user_b_id)
select
    least(a.id, b.id),
    greatest(a.id, b.id)
from match_seed s
join users a on a.telegram_id = s.user_a_telegram_id
join users b on b.telegram_id = s.user_b_telegram_id
on conflict do nothing;

select
    count(*) as seeded_users
from users
where telegram_id between 900001 and 900012;
