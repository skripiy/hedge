# Техническое задание: Volume Farming Bot (VolumeBot)

## 1. Цель проекта

Создание торгового бота для **накопления торгового объёма** на криптовалютных биржах. В отличие от классического хеджинга (где цель — заработок на спреде), данная стратегия оптимизирует три ключевых метрики:

| Приоритет | Метрика | Цель |
|-----------|---------|------|
| 🥇 **1** | **Торговый объём** | Максимизировать (position_size × 2 за каждую сделку) |
| 🥈 **2** | **Расхождение PnL** | Держать PnL на биржах как можно дальше от нуля (например, +400 / -400) |
| 🥉 **3** | **Длительность позиций** | Удерживать открытыми минимум 1 час |

---

## 2. Бизнес-логика стратегии

### 2.1. Расчёт торгового объёма

```
Volume = Position_Size_USDT × 2 × Leverage
```

**Пример:**
- Position Size: 100 USDT
- Leverage: 10x
- Одна сделка (открытие + закрытие) = **2,000 USDT объёма**

### 2.2. Расхождение PnL (PnL Divergence)

Цель: создать максимальный "разрыв" между PnL на разных биржах.

```
Exchange A PnL: +400 USDT
Exchange B PnL: -400 USDT
Net PnL:        ~0 USDT (нейтрально)
Divergence:     800 USDT ✓ (чем больше — тем лучше)
```

**Зачем это нужно:**
- Для достижения VIP-статуса на биржах
- Для получения ребейтов (rebates) от объёма
- Для участия в программах маркет-мейкинга

### 2.3. Правила удержания позиций

| Параметр | Значение | Описание |
|----------|----------|----------|
| `min_hold_time` | 60 минут | Минимальное время удержания |
| `max_hold_time` | 8 часов | Максимальное время (ночной close) |
| `close_on_convergence` | false | НЕ закрывать при сходимости цен |
| `close_trigger` | timer_only | Закрывать только по таймеру |

---

## 3. Стратегия покрытия издержек (Break-Even First)

> **Ключевой принцип:** Генерировать объём БЕЗ убытков. Закрывать только когда позиция покрывает все комиссии.

### 3.1. Расчёт точки безубыточности

```
Break-Even Spread = (Taker_Fee × 4) + Slippage × 2

Пример:
  Taker Fee: 0.05%
  Slippage:  0.02%
  Break-Even = (0.05% × 4) + (0.02% × 2) = 0.24%
```

**4 комиссии:** Open Long + Open Short + Close Long + Close Short

### 3.2. Правило входа

```python
# Входим только если текущий спред >= Break-Even
if current_spread >= break_even_spread:
    open_position()
```

| Параметр | Значение | Описание |
|----------|----------|----------|
| `min_entry_spread` | break_even + buffer | Минимум для входа |
| `buffer_percent` | 0.05% | Запас на волатильность |
| `effective_min_spread` | ~0.30% | Итоговый порог входа |

### 3.3. Правило выхода (Гибридное)

Закрываем позицию когда выполнены **ОБА** условия:

```python
if elapsed_time >= min_hold_time AND net_pnl >= 0:
    close_position()

# Или если прибыль достаточна раньше времени:    
if net_pnl >= target_profit:
    close_position()
```

| Триггер | Условие | Приоритет |
|---------|---------|-----------|
| Time + Profit | time ≥ 60m AND pnl ≥ 0 | Основной |
| Early Profit | pnl ≥ +0.1% | Досрочный |
| Emergency SL | pnl ≤ -2% | Защитный |
| Max Hold | time ≥ 8h | Принудительный |

---

## 4. Модель безубыточности

### 4.1. Калькулятор комиссий

```
Per Trade Costs:
├── Open Long:   100 USDT × 0.05% = 0.05 USDT
├── Open Short:  100 USDT × 0.05% = 0.05 USDT
├── Close Long:  100 USDT × 0.05% = 0.05 USDT
├── Close Short: 100 USDT × 0.05% = 0.05 USDT
├── Slippage:    ~0.04 USDT
└── TOTAL:       0.24 USDT на 100 USDT позицию
```

### 4.2. Минимальная прибыль для закрытия

```python
min_profit_to_close = total_fees = 0.24 USDT

# Закрываем только если:
if position.unrealized_pnl >= min_profit_to_close:
    close_with_profit()
```

### 4.3. Использование Maker ордеров

Maker fee обычно ниже (0.02% vs 0.05%):

```
С Maker ордерами:
  Fee: 0.02% × 4 = 0.08%
  Break-Even: 0.08% + 0.04% = 0.12%
  
Экономия: 0.24% - 0.12% = 0.12% на каждой сделке
```

---

## 5. Метрики и KPI (обновлённые)

### 5.1. Основные метрики

| Метрика | Формула | Цель |
|---------|---------|------|
| Daily Volume | Σ(position_size × 2 × leverage) | > 100,000 USDT/день |
| PnL Divergence | abs(PnL_A) + abs(PnL_B) | > 500 USDT |
| Avg Hold Time | avg(close_time - open_time) | > 60 минут |
| Trade Count | count(closed_positions) | > 30/день |
| **Net PnL** | PnL_A + PnL_B - fees | **≥ 0 (НЕ уходить в минус)** |
| Win Rate | profitable_trades / total | > 80% |

### 5.2. Правило безубыточности

```
🚫 ЗАПРЕЩЕНО: Закрывать позицию в минус (кроме Emergency SL)
✅ РАЗРЕШЕНО: Держать позицию дольше, пока не выйдет в плюс
```

### 5.3. Дашборд метрик

```
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ TODAY'S VOLUME  │ │ PNL DIVERGENCE  │ │ AVG HOLD TIME   │
│   $87,500       │ │   $623          │ │   1h 45m        │
│ Target: 100K    │ │ A: +312 B: -311 │ │ Target: 1h+     │
└─────────────────┘ └─────────────────┘ └─────────────────┘

┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ TRADES TODAY    │ │ NET PNL         │ │ WIN RATE        │
│   32            │ │   +$12          │ │   94%           │
│ All profitable  │ │ ✅ Above zero   │ │ 30/32 winners   │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

---

## 6. Изменения в коде

### 6.1. Новые поля в BotConfig

```python
class BotConfig:
    # Volume Farming Settings
    strategy_mode = Column(Enum("hedge", "volume_farming"), default="volume_farming")
    min_hold_time_minutes = Column(Integer, default=60)
    max_hold_time_minutes = Column(Integer, default=480)
    close_on_convergence = Column(Boolean, default=False)
    target_daily_volume = Column(Float, default=100000.0)
    max_pnl_divergence = Column(Float, default=2000.0)
```

### 6.2. Новые поля в Trade

```python
class Trade:
    # Additional metrics
    volume_generated = Column(Float)  # position_size × 2 × leverage
    hold_duration_seconds = Column(Integer)
    pnl_divergence_at_close = Column(Float)
```

### 6.3. Новая логика в Strategy

```python
class VolumeStrategy:
    async def should_close(self, position) -> Tuple[bool, str]:
        """Определяет нужно ли закрывать позицию"""
        elapsed = datetime.now() - position.open_time
        net_pnl = position.unrealized_pnl
        min_profit = self.calculate_min_profit(position)  # комиссии
        
        # 1. Защитный стоп-лосс
        if net_pnl <= -self.emergency_stop_loss:
            return True, "emergency_stop_loss"
        
        # 2. Принудительное закрытие по макс. времени
        if elapsed >= timedelta(hours=8):
            return True, "max_hold_time_forced"
        
        # 3. Основной триггер: время + прибыль
        if elapsed >= timedelta(minutes=self.min_hold_time):
            if net_pnl >= min_profit:  # Покрывает комиссии
                return True, "profitable_close"
            # Продолжаем держать - ждём выхода в плюс
        
        # 4. Досрочное закрытие при хорошей прибыли
        if net_pnl >= self.target_profit:
            return True, "early_profit_take"
        
        return False, "holding_for_profit"
```

---

## 7. Пример торгового дня (Break-Even Strategy)

### Сессия Volume Farming с покрытием издержек

**Настройки:**
- Position Size: 500 USDT
- Leverage: 10x
- Min Hold Time: 60 минут
- Min Entry Spread: 0.30% (покрывает комиссии)
- Close only if profitable: ✅

**Ход торговли:**

```
08:00 [SCAN] BTC/USDT: Spread 0.25% < 0.30% → SKIP (не покрывает комиссии)
08:01 [SCAN] ETH/USDT: Spread 0.42% > 0.30% → ENTRY ✓
       Open: Binance LONG $3,200 | Bybit SHORT $3,213

08:05 [SCAN] SOL/USDT: Spread 0.35% > 0.30% → ENTRY ✓
08:12 [SCAN] XRP/USDT: Spread 0.28% < 0.30% → SKIP

09:01 [CHECK] ETH/USDT: Elapsed 60m, PnL: +$0.85 > min_profit $0.60 → CLOSE ✓
       Volume: +10,000 USDT
       Net PnL: +$0.85 ✅

09:05 [CHECK] SOL/USDT: Elapsed 60m, PnL: -$0.20 < 0 → HOLD (ждём плюса)
09:45 [CHECK] SOL/USDT: Elapsed 100m, PnL: +$0.42 < $0.60 → HOLD
10:30 [CHECK] SOL/USDT: Elapsed 145m, PnL: +$0.75 > $0.60 → CLOSE ✓
       Volume: +10,000 USDT
       Net PnL: +$0.75 ✅

... (продолжение) ...

23:59 [SUMMARY]
       Total Trades: 28 (меньше, но все прибыльные)
       Total Volume: 280,000 USDT
       Net PnL: +$18.50 ✅ (НЕ в минусе!)
       Fees Paid: $84
       Win Rate: 100% (28/28)
       Avg Hold Time: 1h 52m ✅
       PnL Divergence: A: +245, B: -227 = 472 USDT ✅
```

---

## 8. Риски и митигация

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| Funding Rate | Высокая | Переключение направления long/short |
| Ликвидация | Низкая (хедж) | Emergency SL на -2% |
| Долгое удержание | Средняя | Max hold time 8h принудительно |
| Застрявшие позиции | Средняя | Градуальное снижение min_profit |
| API rate limits | Средняя | Throttling, retry logic |

---

## 9. Сравнение стратегий

| Аспект | Классический Hedge | Volume (агрессивный) | Volume (break-even) |
|--------|-------------------|---------------------|---------------------|
| **Цель** | Прибыль | Объём любой ценой | Объём без убытков |
| **Триггер входа** | Spread > 0.5% | Spread > 0.01% | Spread > 0.30% |
| **Триггер выхода** | Сходимость | Таймер | Таймер + PnL ≥ 0 |
| **Net PnL** | Положительный | Может быть минус | Всегда ≥ 0 |
| **Volume** | Низкий | Максимальный | Умеренный |

---

## 10. План реализации

### Этап 1: Модификация моделей
- [ ] Добавить `min_entry_spread` (расчётный)
- [ ] Добавить `close_only_if_profitable` флаг
- [ ] Добавить метрики win_rate, hold_duration

### Этап 2: Стратегия Break-Even
- [ ] Расчёт точки безубыточности
- [ ] Логика входа: spread ≥ break_even
- [ ] Логика выхода: time ≥ min AND pnl ≥ 0

### Этап 3: UI обновления
- [ ] Карточки Volume/Divergence/WinRate
- [ ] Настройка break-even параметров
- [ ] Индикатор "ждём выхода в плюс"

### Этап 4: Тестирование
- [ ] Simulation: проверить 0 убыточных сделок
- [ ] Проверить застрявшие позиции
- [ ] Оптимизация hold time

---

## 11. Конфигурация по умолчанию

```json
{
  "strategy_mode": "volume_break_even",
  "position_size_usdt": 500,
  "leverage": 10,
  "min_hold_time_minutes": 60,
  "max_hold_time_minutes": 480,
  "min_entry_spread_percent": 0.30,
  "close_only_if_profitable": true,
  "min_profit_percent": 0.12,
  "target_daily_volume": 100000,
  "max_concurrent_positions": 5,
  "emergency_stop_loss_percent": 2.0,
  "max_daily_loss": 500,
  "use_maker_orders": true
}
```
