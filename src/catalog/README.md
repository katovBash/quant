# Сборка исторических обзоров

`build_strategy_tables.py` собирает `results.csv`, `build_strategy_readmes.py` — сводки и топ‑5 в [`experiments/.history/rule-reviews`](../../experiments/.history/rule-reviews/README.md). `check_ema_layout.py` проверяет, что в `strategies/` остаётся только выбранный код, а 21 исторический обзор по 258 тикерам находится в экспериментах. `migrate_strategy_layout.py` и `migrate_to_experiments.py` — уже выполненные одноразовые переносы; повторно запускать их не нужно.

Запускать из корня: `python3 -m src.catalog.check_ema_layout`. Источник данных и ограничения конкретного отчёта указаны в README обзора. Создание таблицы не означает, что все 258 тикеров проверены: отсутствующие тесты помечены `not_tested`.
