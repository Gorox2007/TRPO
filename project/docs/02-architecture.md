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
    C->>C: score = primary + behavior + referral
    C-->>B: лучший кандидат
    B-->>U: карточка кандидата
```

## 2.4 Формула скоринга Этапа 3

`total_score = 0.65 * primary_score + 0.30 * behavioral_score + 0.05 * referral_score`

Где:
- `primary_score`: возраст, пол, город, полнота анкеты и фото;
- `behavioral_score`: лайки, пропуски и мэтчи;
- `referral_score`: бонус за приглашенных пользователей.
