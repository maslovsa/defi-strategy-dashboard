Ты — эксперт по DeFi-анализу и дашбордам. Создай полный интерактивный дашборд на Python (используй Streamlit + Plotly для простоты развертывания) для анализа стратегии "AAVE collateral + borrow + Uniswap V3 LP + collect fees".

**Данные стратегии (пример):**
- Депозит ETH в AAVE: 75.1000 ETH ($184,143.70 при цене $2,451.98).
- Займ: $100,000 (USDC/USDT).
- Купить ETH на $21,000 → 8.9000 ETH ($21,822.62).
- Создать Uniswap V3 позицию ETH/USDC: 8.9000 ETH + 78,339.3784 USDT ($78,250.07).
- Ожидаемый доход: ~$5000/мес от collect fees.

**Реальный адрес кошелька для анализа:** 0x6b0f1267f2c7a633c639fb525a400a55f8d78888 (проанализируй его транзакции на Etherscan/Dune для похожих стратегий).

**Задача: собери дашборд с 1 раза. Код должен быть полным, готовым к запуску (pip install streamlit plotly pandas requests).**

**Структура дашборда (обязательно все секции):**

1. **Инпуты (sidebar):**
   - ETH цена (default: 2451.98 USD).
   - Депозит ETH (default: 75.1).
   - LTV borrow % (default: 70-80%).
   - Uniswap fee tier (0.3%).
   - Range позиции (±10-20%).
   - Месяцы симуляции (12).
   - Кнопка "Загрузить данные кошелька 0x6b0f...".

2. **Секция 1: Анализ кошелька**
   - Таблица топ-транзакций (AAVE supply/borrow, Uniswap mint/collect).
   - График баланса ETH/USDC/Aave positions.
   - Метрики: total fees collected, avg monthly yield.

3. **Секция 2: Калькулятор стратегии**
   - Таблица breakdown:
     | Шаг | Действие | Сумма ETH | Сумма USD | Health Factor |
     |-----|----------|-----------|-----------|---------------|
   - Расчёт: collateral value, borrow amount, LP size, expected fees (на основе исторических APR Uniswap ETH/USDC).

4. **Секция 3: Симуляция P&L**
   - График (Plotly): Cumulative fees, IL, borrow interest, net profit (monte-carlo с волатильностью ETH ±30%).
   - Метрики: APR, max drawdown, liquidation risk.

5. **Секция 4: Риски**
   - Bullet-list: IL, liquidation при ETH drop 50%, borrow rates.
   - Кнопка "Stress-test".

**Логика расчётов:**
- Collateral value = ETH_amount * price * LTV.
- LP fees = (TVL * fee_tier * volume_share * 12) / 365 * months. (Используй Dune API или hardcode avg 20-50% APR для ETH/USDC).
- Для кошелька: fetch tx via Etherscan API (бесплатно, key не нужен для demo).
- Health Factor = (Collateral * LT) / Borrow.

**Вывод:** Полный код дашборда. Запусти его локально: streamlit run app.py. Добавь markdown с выводами анализа стратегии (yield 25-40% APR, но high risk).

Сделай код чистым, с функциями. Нет ошибок, сразу работает. Начни с: import streamlit as st ...
