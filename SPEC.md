# Техническое задание: Дельта-нейтральный Торговый Бот (HedgeBot)

## 1. Цель проекта
Создание программного комплекса для автоматизированного открытия и сопровождения дельта-нейтральных позиций (хеджирования) на криптовалютных биржах. Система должна поддерживать два режима работы: **симуляция** (Paper Trading) на реальных данных и **реальная торговля** (Live Trading).

## 2. Архитектура системы
Система состоит из трех основных модулей, обернутых в Docker-контейнеры:

1.  **Core Trading Engine (Backend/Bot):** Python-скрипт. Отвечает за подключение к биржам, логику входа/выхода, риск-менеджмент и расчет симуляции.
2.  **Web API & Database:** REST API (FastAPI) для связи фронтенда с ботом и PostgreSQL для хранения истории сделок, настроек и конфигураций.
3.  **Web Frontend (UI):** Панель управления для мониторинга, настройки стратегий и переключения режимов.

## 3. Функциональные требования

### 3.1. Режимы работы ✅
Система должна иметь глобальный переключатель режима для каждой запущенной стратегии.

#### А. Режим Симуляции (Paper Trading) ✅
* ✅ Пользователь задает `Virtual Balance` (например, 10,000 USDT).
* ✅ Бот получает реальные котировки через REST API (ccxt).
* ✅ При "входе" в сделку бот **не отправляет** ордера на биржу, а записывает точку входа в БД.
* ✅ **Важно:** Симуляция учитывает комиссии (Taker/Maker fee) и примерное проскальзывание (Slippage), вычитая их из виртуального баланса.

#### Б. Режим Реальной Торговли (Live) ✅
* ✅ Использование API Key / Secret для отправки реальных ордеров.
* ✅ Проверка реальных балансов на биржах перед входом.

### 3.2. Политики торговли (Trading Policies) ✅
Пользователь настраивает логику через веб-интерфейс:

* **Параметры входа:** ✅
    * ✅ *Тип:* Market ордер (реализовано), Limit (подготовлено).
    * ✅ *Триггер:* Разница цен между биржами < `X%` (spread_threshold).
    * ✅ *Объем:* Фиксированный (в USDT) или `%` от депозита.
* **Выбор пар и бирж:** ✅
    * ✅ Биржа А (Long) vs Биржа Б (Short) - настраивается.
    * ✅ Инструменты - мульти-символьная торговля (BTC/USDT, ETH/USDT и др.).
* **Риск-менеджмент (синхронный выход):** ✅
    * ✅ *Global Stop-Loss:* Если суммарный PnL достигает `-X USDT`.
    * ✅ *Global Take-Profit:* Если суммарный PnL достигает `+Y USDT`.
    * ✅ *Per-symbol Stop-Loss/Take-Profit:* Индивидуальные лимиты для каждого символа.
    * ✅ *Emergency Close:* Кнопка "Panic Button" в веб-интерфейсе для мгновенного закрытия всех позиций.
    * ✅ *Max Daily Loss:* Остановка торговли при достижении дневного лимита убытков.
    * ✅ *Max Position Duration:* Автоматическое закрытие по времени.

### 3.3. Логика исполнения (Execution Engine) ✅
* ✅ **Синхронность:** Использование `asyncio.gather` для параллельной отправки ордеров на обе биржи.
* ✅ **Rollback Mechanism (Механизм отката):**
    * Логика: Если на *Бирже А* ордер прошел, а на *Бирже Б* возникла ошибка -> Бот **мгновенно** закрывает позицию на *Бирже А* (Market Close).

## 4. Веб-интерфейс (UI) ✅
**Стек:** React (Vite) + TradingView Lightweight Charts.

### 4.1. Дашборд (Главная страница) ✅
* **Карточки состояния:** ✅
    * ✅ Текущий PnL (Нереализованная прибыль/убыток).
    * ✅ Баланс (Виртуальный или Реальный).
    * ✅ Статус соединения с биржами.
    * ✅ Количество открытых позиций.
* **Активные позиции:** ✅ Таблица с колонками:
    * `Биржа` | `Сторона` | `Цена входа` | `Текущая цена` | `PnL ноги` | `Суммарный PnL`
* **Лог действий:** ✅ Консольный вывод последних действий бота.
* **Панель решений бота:** ✅ Decision Log с отображением процесса принятия решений.
* **Котировки в реальном времени:** ✅ Отображение bid/ask/spread для отслеживаемых символов.

### 4.2. Страница настройки (Config/Settings) ✅
* ✅ Ввод API Keys.
* ✅ Переключатель режима (Simulation / Live).
* ✅ Поля: `Initial Deposit`, `Leverage`, `Stop Loss %`, `Take Profit %`.
* ✅ Настройка комиссий и проскальзывания.
* ✅ **Auto-Trade:** Переключатель автоматической торговли.

### 4.3. Страница управления символами (Symbols) ✅
* ✅ Добавление/удаление торговых пар.
* ✅ Индивидуальные настройки для каждого символа (leverage, position size, stop-loss, take-profit).
* ✅ Включение/выключение торговли по каждому символу.

### 4.4. Страница аналитики ✅
* ✅ График изменения баланса во времени (Equity curve).
* ✅ История сделок.
* ✅ Статистика: общий PnL, Win Rate, средний PnL, Profit Factor.

### 4.5. Страница логов ✅
* ✅ Фильтрация по уровню (INFO, WARNING, ERROR).
* ✅ Поиск по сообщениям.

## 5. Технический стек и инструменты

### Backend (Python) ✅
* **Язык:** Python 3.11+
* **Библиотеки:**
    * ✅ `ccxt` (async version) — взаимодействие с биржами.
    * ✅ `FastAPI` — веб-сервер для UI и API.
    * ✅ `pydantic` — валидация данных конфигурации.
    * ✅ `sqlalchemy` + `asyncpg` — асинхронная работа с БД.

### База данных ✅
* **PostgreSQL:**
    * ✅ Table `bot_configs`: конфигурации бота.
    * ✅ Table `symbol_configs`: настройки по символам.
    * ✅ Table `trades`: история сделок с PnL.
    * ✅ Table `decisions`: лог решений бота.
    * ✅ Table `logs`: системные сообщения.
    * ✅ Table `price_cache`: кэш цен.

### Инфраструктура ✅
* ✅ **Docker Compose:** Оркестрация контейнеров `bot`, `web_api`, `frontend`.
* ✅ **Nginx:** Прокси-сервер для продакшена.

## 6. API Endpoints ✅

### Контроль бота
* ✅ `POST /start` — Запуск бота
* ✅ `POST /stop` — Остановка бота
* ✅ `POST /panic-close` — Экстренное закрытие всех позиций
* ✅ `GET /status` — Текущий статус бота

### Позиции и сделки
* ✅ `GET /positions` — Список открытых позиций
* ✅ `POST /positions/{trade_id}/close` — Закрыть конкретную позицию
* ✅ `GET /trades` — История сделок
* ✅ `GET /trades/{trade_id}` — Детали сделки

### Конфигурация
* ✅ `GET /config` — Получить конфигурацию
* ✅ `PUT /config` — Обновить конфигурацию
* ✅ `POST /config` — Создать новую конфигурацию

### Символы (мульти-символьная торговля)
* ✅ `GET /symbols` — Список настроенных символов
* ✅ `POST /symbols` — Добавить символ
* ✅ `PUT /symbols/{id}` — Обновить настройки символа
* ✅ `DELETE /symbols/{id}` — Удалить символ

### Аналитика
* ✅ `GET /equity-curve` — Данные для графика equity
* ✅ `GET /analytics/summary` — Сводная статистика

### Логи и решения
* ✅ `GET /logs` — Системные логи
* ✅ `GET /decisions` — Лог решений бота

### Рынки
* ✅ `GET /markets` — Доступные рынки с бирж
* ✅ `GET /prices` — Текущие цены

## 7. Структура проекта ✅

```text
hedge/
├── docker-compose.yml       # Запуск всей инфраструктуры
├── .env.example             # Пример переменных окружения
├── requirements.txt         # Зависимости Python
├── Dockerfile.backend       # Dockerfile для API
├── Dockerfile.bot           # Dockerfile для бота
├── bot/                     # Core Trading Engine
│   ├── __init__.py
│   ├── main.py              # Точка входа бота (HedgeBot class)
│   ├── exchange.py          # ExchangeManager (CCXT wrapper)
│   ├── strategy.py          # Strategy, HedgePosition (логика входа/выхода)
│   ├── risk_manager.py      # RiskManager (стопы, лимиты)
│   └── db_service.py        # Сервис работы с БД
├── backend/                 # API Server
│   ├── __init__.py
│   ├── app.py               # FastAPI app (все endpoints)
│   ├── models.py            # SQLAlchemy модели
│   ├── schemas.py           # Pydantic схемы
│   └── database.py          # Подключение к PostgreSQL
├── frontend/                # UI (Vite + React)
│   ├── Dockerfile
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx          # Роутинг
│       ├── main.jsx         # Точка входа
│       ├── index.css        # Стили (темная тема)
│       ├── api/             # API клиент
│       ├── hooks/           # React hooks
│       ├── components/      # UI компоненты
│       │   ├── ControlPanel.jsx    # Панель управления
│       │   ├── DecisionsPanel.jsx  # Лог решений
│       │   ├── EquityChart.jsx     # График equity
│       │   ├── LogsPanel.jsx       # Панель логов
│       │   ├── PositionsTable.jsx  # Таблица позиций
│       │   ├── RatesPanel.jsx      # Котировки
│       │   ├── Sidebar.jsx         # Боковое меню
│       │   └── StatCard.jsx        # Карточки статистики
│       └── pages/           # Страницы
│           ├── Dashboard.jsx   # Главная
│           ├── Settings.jsx    # Настройки
│           ├── Symbols.jsx     # Управление символами
│           ├── Analytics.jsx   # Аналитика
│           ├── Positions.jsx   # Позиции
│           └── Logs.jsx        # Логи
└── nginx/                   # Nginx конфигурация
    └── nginx.conf
```

## 8. План разработки (Roadmap)

### Этап 1: Ядро (Core) ✅ ЗАВЕРШЕН
* ✅ Реализация класса `ExchangeManager` (ccxt wrapper).
* ✅ Функция `simulate_order` с учетом комиссий.
* ✅ `Strategy` класс для управления хедж-позициями.
* ✅ `RiskManager` для мониторинга и автоматического закрытия.
* ✅ Rollback Mechanism при частичном исполнении.

### Этап 2: База и API ✅ ЗАВЕРШЕН
* ✅ Настройка PostgreSQL + Docker.
* ✅ SQLAlchemy модели (BotConfig, SymbolConfig, Trade, Decision, Log).
* ✅ API Endpoints: `/start`, `/stop`, `/status`, `/config`, `/positions`, `/trades`.
* ✅ Мульти-символьная торговля.

### Этап 3: Веб-интерфейс ✅ ЗАВЕРШЕН
* ✅ Верстка Dashboard с карточками статистики.
* ✅ Интеграция с API (опрос статуса в реальном времени).
* ✅ Страница настроек с возможностью редактирования.
* ✅ Страница управления торговыми парами.
* ✅ Страница аналитики с графиками.
* ✅ Темная премиум-тема.

### Этап 4: Реальная торговля ✅ ПОДГОТОВЛЕНО
* ✅ Подключение боевых методов `create_order` через ccxt.
* ✅ Реализация и тест `Rollback Mechanism`.
* ⬜ Тестирование на Testnet биржи.
* ⬜ Деплой на продакшен.

## 9. Статус реализации

| Компонент | Статус | Примечание |
|-----------|--------|------------|
| ExchangeManager | ✅ | CCXT wrapper, simulation + live |
| Strategy | ✅ | Delta-neutral hedging logic |
| RiskManager | ✅ | SL/TP, daily limits, halt trading |
| Database Models | ✅ | PostgreSQL + SQLAlchemy |
| FastAPI Backend | ✅ | Все endpoints реализованы |
| React Frontend | ✅ | Dashboard, Settings, Symbols, Analytics |
| Docker Compose | ✅ | bot + web_api + frontend |
| Nginx | ✅ | Proxy для продакшена |
| Decision Log | ✅ | Отслеживание решений бота |
| Multi-symbol | ✅ | Торговля несколькими парами |
| Auto-trade | ✅ | Автоматическое открытие позиций |

## 10. Примеры торговых сценариев

### Пример 1: Успешная дельта-нейтральная сделка

**Начальные условия:**
- Баланс: 10,000 USDT
- Символ: BTC/USDT
- Position Size: 100 USDT
- Leverage: 1x
- Spread Threshold: 0.5%

**Шаг 1: Обнаружение возможности**
```
Binance BTC/USDT: Ask = 95,000 USDT
Bybit BTC/USDT:   Bid = 95,600 USDT
Spread = (95,600 - 95,000) / 95,000 * 100 = 0.63% > 0.5% ✓
```

**Шаг 2: Открытие позиции**
```
Exchange A (Binance): LONG  0.00105 BTC @ 95,000 = 100 USDT
Exchange B (Bybit):   SHORT 0.00105 BTC @ 95,600 = 100 USDT

Комиссии (Taker 0.1%): 0.10 + 0.10 = 0.20 USDT
Slippage (0.05%):      0.05 + 0.05 = 0.10 USDT
Итого расходы: 0.30 USDT
```

**Шаг 3: Закрытие при сходимости цен**
```
Binance: 95,300 USDT (продаём LONG)
Bybit:   95,350 USDT (покупаём SHORT)

PnL Exchange A: (95,300 - 95,000) * 0.00105 = +0.315 USDT
PnL Exchange B: (95,600 - 95,350) * 0.00105 = +0.263 USDT

Gross PnL: +0.578 USDT
Fees:      -0.30 USDT
Net PnL:   +0.278 USDT ✅
```

---

### Пример 2: Срабатывание Stop-Loss

**Настройки:**
- Stop-Loss: 2%
- Position Size: 500 USDT

**Ситуация: Резкое расхождение цен**
```
Вход:
  Binance LONG  @ 95,000
  Bybit   SHORT @ 95,600

Текущие цены (неблагоприятное движение):
  Binance: 94,000 (-1.05%)
  Bybit:   96,500 (+0.94%)

PnL LONG:  (94,000 - 95,000) / 95,000 * 500 = -5.26 USDT
PnL SHORT: (95,600 - 96,500) / 95,600 * 500 = -4.71 USDT
Total PnL: -9.97 USDT = -1.99% от позиции

Trigger: -2% достигнут → АВТОЗАКРЫТИЕ ⚠️
```

**Действие бота:**
1. Логирует решение: `decision_type=RISK, action=stop_loss_triggered`
2. Закрывает обе ноги параллельно (`asyncio.gather`)
3. Фиксирует убыток в БД
4. Обновляет `current_balance`

---

### Пример 3: Take-Profit на профитной позиции

**Настройки:**
- Take-Profit: 5%
- Position Size: 200 USDT

**Вход:**
```
Binance LONG  @ 3,200 USDT (ETH)
Bybit   SHORT @ 3,230 USDT
Spread at entry: 0.94%
```

**Сходимость цен (идеальный сценарий):**
```
Binance: 3,220 USDT
Bybit:   3,218 USDT

PnL LONG:  (3,220 - 3,200) / 3,200 * 200 = +1.25 USDT
PnL SHORT: (3,230 - 3,218) / 3,230 * 200 = +0.74 USDT
Total PnL: +1.99 USDT = +1.0%
```

**Spread схлопнулся еще сильнее:**
```
Binance: 3,250 USDT
Bybit:   3,245 USDT

PnL LONG:  +3.13 USDT
PnL SHORT: -0.93 USDT
Total PnL: +2.20 USDT = +1.1%
```

**Накопительный эффект (несколько итераций):**
```
После 5 успешных циклов:
Total realized PnL: +12.50 USDT = +6.25% > 5%
Trigger: Take-Profit → Позиция закрыта с прибылью ✅
```

---

### Пример 4: Rollback при ошибке исполнения

**Сценарий: Ордер на одной бирже не прошел**

**Шаг 1: Попытка открытия**
```python
# Параллельная отправка ордеров
results = await asyncio.gather(
    exchange_a.create_order("BTC/USDT", "market", "buy", 0.001),
    exchange_b.create_order("BTC/USDT", "market", "sell", 0.001),
    return_exceptions=True
)
```

**Шаг 2: Результат**
```
Order A (Binance): SUCCESS ✅
  order_id: "12345"
  filled: 0.001 BTC @ 95,000

Order B (Bybit): FAILED ❌
  error: "Insufficient margin"
```

**Шаг 3: Rollback (автоматический откат)**
```python
# Бот обнаруживает частичное исполнение
if order_a.success and not order_b.success:
    # Немедленно закрываем успешную ногу
    await exchange_a.close_position("BTC/USDT", "long", 0.001)
```

**Лог:**
```
[WARNING] Partial execution detected. Rolling back...
[INFO] Closed LONG position on Binance: -0.15 USDT (slippage + fees)
[ERROR] Position opening failed: Bybit - Insufficient margin
```

**Итог:**
- Позиция не открыта
- Убыток от rollback: ~0.15 USDT (комиссия + проскальзывание за закрытие)
- Направленный риск устранён ✅

---

### Пример 5: Daily Loss Limit

**Настройки:**
- Max Daily Loss: 50 USDT
- Virtual Balance: 1,000 USDT

**Ход торговли за день:**
```
Trade 1: -8.50 USDT (stop-loss)
Trade 2: +3.20 USDT (profit)
Trade 3: -12.30 USDT (stop-loss)
Trade 4: +5.10 USDT (profit)
Trade 5: -25.00 USDT (stop-loss)
Trade 6: -15.00 USDT (stop-loss)

Running Daily PnL:
  -8.50 → -5.30 → -17.60 → -12.50 → -37.50 → -52.50 USDT
```

**Trigger при Trade 6:**
```
Daily Loss = -52.50 USDT > -50 USDT limit
→ TRADING HALTED ⛔
```

**Действие RiskManager:**
1. Устанавливает `trading_halted = True`
2. Закрывает все открытые позиции
3. Логирует: `"Daily loss limit reached. Trading halted."`
4. Отправляет уведомление через API

**Возобновление:**
- Автоматически в 00:00 UTC следующего дня
- Или вручную через `POST /resume-trading`

---

### Пример 6: Мульти-символьная торговля

**Настроенные символы:**
| Символ | Enabled | Position Size | Spread Threshold | Stop-Loss |
|--------|---------|---------------|------------------|-----------|
| BTC/USDT | ✅ | 200 USDT | 0.3% | 2% |
| ETH/USDT | ✅ | 100 USDT | 0.5% | 3% |
| SOL/USDT | ❌ | 50 USDT | 0.8% | 5% |

**Бот сканирует все enabled символы:**
```
[SCAN] BTC/USDT: Spread 0.25% < 0.3% → SKIP
[SCAN] ETH/USDT: Spread 0.62% > 0.5% → OPPORTUNITY FOUND
[ENTRY] ETH/USDT: Opening hedge position...
  - Binance LONG  0.031 ETH @ 3,200
  - Bybit   SHORT 0.031 ETH @ 3,220
[SUCCESS] Position opened: ETH-hedge-abc123
```

**Параллельный мониторинг:**
```
Active positions:
  1. BTC-hedge-xyz789: PnL +1.50 USDT (open 2h)
  2. ETH-hedge-abc123: PnL -0.30 USDT (open 5m)

Total Unrealized PnL: +1.20 USDT
```