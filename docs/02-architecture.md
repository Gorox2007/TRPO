# 2. Архитектура и дизайн системы (упрощенно)

## 2.1 Подход для учебного проекта

Используем **один монолит**:
- Telegram Bot (входные события);
- Core-логика (анкета, предпочтения, подбор, лайки/матчи);
- PostgreSQL (все данные).

## 2.2 Контекстная схема

```mermaid
flowchart LR
    U[Пользователь Telegram] --> TG[Telegram Bot API]
    TG --> APP[Dating Bot Monolith]
    APP --> DB[(PostgreSQL)]
```


## 2.3 Сценарий "получить кандидата"

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant B as Bot
    participant C as Core
    participant D as DB

    U->>B: /next
    B->>C: запрос кандидата для user_id
    C->>D: профиль + предпочтения + уже просмотренные
    D->>C: пул кандидатов по фильтрам
    C->>C: score = prefs + completeness + photos + geo
    C-->>B: лучший кандидат
    B-->>U: карточка кандидата
```

## 2.4 Черновая формула скоринга

`total_score = 0.50 * geo_score + 0.25 * preference_score + 0.15 * completeness_score + 0.10 * photo_score`

Где:
- `preference_score`: совпадение по полу/возрасту;
- `completeness_score`: полнота анкеты;
- `photo_score`: нормализованный балл по количеству фото;
- `geo_score`: близость по городу/координатам.
