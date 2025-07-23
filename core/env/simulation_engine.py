from __future__ import annotations
from .models import WorldState
from . import wave_manager, dispatcher_heuristic, progress_model, metrics
from . import client_scheduler
from . import inbound_scheduler
from .event_bus import EventBus
# from core.agents.emergency_agent.emergency_agent import process as emergency_process
# from core.agents.optimizeras import process as optimizer_process
import random

class SimulationEngine:
    def __init__(self, state: WorldState, cfg: dict):
        self.state = state
        self.cfg = cfg
        self.tick_seconds = cfg["time"]["base_tick_seconds"]
        self.rng = random.Random(state.rng_seed)
        self.event_bus = EventBus()
    
    def _process_docks(self):
        """
        Берём/освобождаем док‑станции.
        Для простоты здесь только задержка; фактическое перемещение товара
        добавьте в finish_inbound() / finish_outbound() при необходимости.
        """
        for dock in self.state.docks.values():

            # закончилась текущая операция
            if dock.status == "busy" and self.state.sim_time >= dock.busy_until:
                dock.status = "free"

            # можно стартовать новую
            if dock.status == "free" and dock.queue:
                _ = dock.queue.pop(0)                            # берём первую фуру
                dock.status = "busy"
                dock.busy_until = self.state.sim_time + dock.service_seconds

    def step(self):
        if self.state.sim_time == 0:
            client_scheduler.publish_initial_inbound(self.state, self.event_bus, self.rng)
            # 0) регулярные inbound
        inbound_scheduler.publish_client_inbound_events(self.state, self.event_bus, self.rng)
        # 1. Периодическая генерация клиентских outbound (пока прямые qty=1; позже добавим qty вариативность)
        if self.state.sim_time % 60 == 0:
            # вместо немедленного создания линий функция теперь должна публиковать события
            self._publish_client_outbound_events()

        # 2. Валидация цикла 1
        self.event_bus.validate_cycle()

        # # 3. Emergency агент (реактивные сплиты больших заказов)
        # emergency_process(self.event_bus, self.state, self.cfg)

        # 4. Повторная валидация (реакции Emergency)
        self.event_bus.validate_cycle()

        # 5. Применяем события -> создаём OrderLine
        self.event_bus.apply_cycle(self.state)

        # ↓ новая обработка доков
        self._process_docks()

        # 6. Waves / Dispatcher / Progress
        wave_manager.update_waves(self.state, self.cfg)
        dispatcher_heuristic.assign_lines(self.state)
        progress_model.advance_progress(self.state, self.tick_seconds)
        
        # 7. Метрики
        metrics.collect_periodic(self.state, self.cfg)
        # optimizer_process(self.state, self.cfg)

        # 8. Время
        self.state.sim_time += self.tick_seconds

    def _publish_client_outbound_events(self):
        """
        Вместо прямого создания линий — публикуем событие OutboundRequest
        по прежней логике (используем schedule_clients_outbound, но модифицируем).
        """
        # Существующая функция schedule_clients_outbound сейчас создаёт напрямую OrderLine.
        # Мы сделаем лёгкий адаптер: скопируем простую часть логики сюда и уберём прямое создание.

        from .client_scheduler import _poisson, _weighted_choice  # используем внутренние функции
        for client in self.state.clients.values():
            if self.state.sim_time < client.next_outbound_time:
                continue
            ob = client.outbound_cfg
            lam = ob['lines_mean']
            batch_count = _poisson(self.rng, lam)
            if batch_count <= 0:
                batch_count = 1
            for _ in range(batch_count):
                sku_id = _weighted_choice(self.rng, client.sku_mix)
                # Qty пока = 1 (можно сделать случайный диапазон позже)
                qty = 1
                self.event_bus.publish(
                    source="client_gen",
                    type_="OutboundRequest",
                    payload={
                        "client_id": client.id,
                        "sku_id": sku_id,
                        "qty": qty
                    },
                    sim_time=self.state.sim_time
                )
            # пересчёт next_outbound_time (логика прежняя)
            pattern = ob['pattern']
            if pattern == "interval":
                base = ob['base_interval_min'] * 60
                j = 0
                if 'jitter_min' in ob and 'jitter_max' in ob:
                    j = self.rng.randint(ob['jitter_min'], ob['jitter_max']) * 60
                client.next_outbound_time = self.state.sim_time + base + j
            elif pattern == "weekly":
                days = ob['days']
                minute_target = ob['time_minute_of_day']
                jitter_min = ob.get('jitter_min', 0)
                jitter_max = ob.get('jitter_max', 0)
                day_sec = 86400
                current_day = self.state.sim_time // day_sec
                minute_of_day = (self.state.sim_time % day_sec) // 60
                for off in range(0, 15):
                    test_day = current_day + off
                    dow = test_day % 7
                    if dow in days:
                        if off == 0 and minute_of_day > minute_target:
                            continue
                        target_time = test_day * day_sec + minute_target * 60
                        j = 0
                        if jitter_min or jitter_max:
                            j = self.rng.randint(jitter_min, jitter_max) * 60
                        target_time += j
                        if target_time <= self.state.sim_time:
                            continue
                        client.next_outbound_time = target_time
                        break
            else:
                client.next_outbound_time = self.state.sim_time + 3600
