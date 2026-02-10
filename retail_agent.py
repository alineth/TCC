#!/usr/bin/env python3
"""Agente simples de apoio à decisão para reposição no varejo.

Uso rápido:
  python retail_agent.py --data sample_demand.csv --validate
  python retail_agent.py --data sample_demand.csv --inventory 140 --on-order 40
"""

from __future__ import annotations

import argparse
import csv
import math
import random
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


SERVICE_Z = {
    0.80: 0.84,
    0.85: 1.04,
    0.90: 1.28,
    0.95: 1.65,
    0.97: 1.88,
    0.99: 2.33,
}


@dataclass
class ReplenishmentDecision:
    forecast_demand: float
    demand_std: float
    estimated_lead_time_days: float
    safety_stock: float
    reorder_point: float
    target_stock: float
    recommended_order_qty: int


class RetailDecisionAgent:
    """Agente de reposição com previsão + política de estoque de segurança.

    - Previsão: média móvel exponencial
    - Incerteza: desvio padrão da janela recente
    - Política: ponto de pedido e estoque-alvo
    """

    def __init__(
        self,
        service_level: float = 0.95,
        review_period_days: int = 7,
        alpha: float = 0.35,
        demand_window: int = 28,
    ) -> None:
        if service_level not in SERVICE_Z:
            valid = ", ".join(str(k) for k in sorted(SERVICE_Z))
            raise ValueError(f"service_level inválido. Use um de: {valid}")
        self.service_level = service_level
        self.review_period_days = review_period_days
        self.alpha = alpha
        self.demand_window = demand_window

    def _exp_smoothing_forecast(self, history: List[float]) -> float:
        if not history:
            return 0.0
        level = history[0]
        for value in history[1:]:
            level = self.alpha * value + (1 - self.alpha) * level
        return max(0.0, level)

    def _recent_std(self, history: List[float]) -> float:
        if len(history) < 2:
            return 0.0
        return statistics.pstdev(history)

    def recommend(
        self,
        demand_history: List[float],
        inventory_on_hand: float,
        inventory_on_order: float,
        lead_time_history: Optional[List[float]] = None,
    ) -> ReplenishmentDecision:
        recent = demand_history[-self.demand_window :] if demand_history else []
        forecast_daily = self._exp_smoothing_forecast(recent)
        demand_std = self._recent_std(recent)

        lead_hist = lead_time_history or [7.0]
        lead_time = max(1.0, statistics.mean(lead_hist))
        z = SERVICE_Z[self.service_level]

        safety_stock = z * demand_std * math.sqrt(lead_time)
        reorder_point = forecast_daily * lead_time + safety_stock

        protection_days = lead_time + self.review_period_days
        target_stock = forecast_daily * protection_days + safety_stock

        net_stock = inventory_on_hand + inventory_on_order
        recommended = max(0.0, target_stock - net_stock)

        return ReplenishmentDecision(
            forecast_demand=forecast_daily,
            demand_std=demand_std,
            estimated_lead_time_days=lead_time,
            safety_stock=safety_stock,
            reorder_point=reorder_point,
            target_stock=target_stock,
            recommended_order_qty=math.ceil(recommended),
        )


def load_demand_csv(path: Path) -> List[float]:
    demand: List[float] = []
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if "demand" not in (reader.fieldnames or []):
            raise ValueError("CSV precisa ter coluna 'demand'.")
        for row in reader:
            demand.append(float(row["demand"]))
    if len(demand) < 10:
        raise ValueError("CSV precisa ter pelo menos 10 linhas de demanda para validação.")
    return demand


def generate_synthetic_demand(days: int = 120, seed: int = 42) -> List[float]:
    random.seed(seed)
    base = 22.0
    output = []
    for d in range(days):
        weekly = 4.5 * math.sin(2 * math.pi * d / 7)
        trend = 0.02 * d
        noise = random.gauss(0, 3.2)
        output.append(max(0.0, base + weekly + trend + noise))
    return output


def run_validation(
    demand: List[float],
    agent: RetailDecisionAgent,
    initial_inventory: float,
    lead_time_days: int = 5,
) -> dict:
    inventory = initial_inventory
    pipeline: List[tuple[int, int]] = []  # (arrival_day, qty)

    stockout_days = 0
    total_shortage = 0.0
    total_holding = 0.0
    placed_orders = 0

    start = max(30, min(45, len(demand) // 3))

    for day in range(start, len(demand)):
        arrivals = [q for arrival, q in pipeline if arrival == day]
        if arrivals:
            inventory += sum(arrivals)
        pipeline = [(arrival, q) for arrival, q in pipeline if arrival != day]

        history = demand[:day]
        on_order = sum(q for _, q in pipeline)
        decision = agent.recommend(
            demand_history=history,
            inventory_on_hand=inventory,
            inventory_on_order=on_order,
            lead_time_history=[lead_time_days],
        )

        if inventory + on_order <= decision.reorder_point:
            qty = decision.recommended_order_qty
            if qty > 0:
                pipeline.append((day + lead_time_days, qty))
                placed_orders += 1

        today_demand = demand[day]
        if inventory >= today_demand:
            inventory -= today_demand
        else:
            shortage = today_demand - inventory
            total_shortage += shortage
            stockout_days += 1
            inventory = 0.0

        total_holding += inventory

    periods = len(demand) - start
    return {
        "periods": periods,
        "stockout_rate": stockout_days / periods if periods else 0.0,
        "avg_ending_inventory": total_holding / periods if periods else 0.0,
        "total_shortage_units": total_shortage,
        "orders_placed": placed_orders,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Agente de reposição para varejo")
    parser.add_argument("--data", type=Path, help="CSV com coluna demand")
    parser.add_argument("--inventory", type=float, default=120.0, help="Estoque atual")
    parser.add_argument("--on-order", type=float, default=20.0, help="Estoque em trânsito")
    parser.add_argument("--service-level", type=float, default=0.95, choices=sorted(SERVICE_Z))
    parser.add_argument("--review-period", type=int, default=7)
    parser.add_argument("--lead-time", type=int, default=5)
    parser.add_argument("--validate", action="store_true", help="Executa validação por simulação")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    demand = load_demand_csv(args.data) if args.data else generate_synthetic_demand()

    agent = RetailDecisionAgent(
        service_level=args.service_level,
        review_period_days=args.review_period,
    )

    decision = agent.recommend(
        demand_history=demand,
        inventory_on_hand=args.inventory,
        inventory_on_order=args.on_order,
        lead_time_history=[args.lead_time],
    )

    print("=== Recomendação do agente ===")
    print(f"Demanda prevista diária: {decision.forecast_demand:.2f}")
    print(f"Desvio padrão estimado: {decision.demand_std:.2f}")
    print(f"Lead time estimado (dias): {decision.estimated_lead_time_days:.2f}")
    print(f"Estoque de segurança: {decision.safety_stock:.2f}")
    print(f"Ponto de pedido: {decision.reorder_point:.2f}")
    print(f"Estoque-alvo: {decision.target_stock:.2f}")
    print(f"Pedido recomendado: {decision.recommended_order_qty} unidades")

    if args.validate:
        metrics = run_validation(
            demand=demand,
            agent=agent,
            initial_inventory=args.inventory,
            lead_time_days=args.lead_time,
        )
        print("\n=== Validação por simulação ===")
        print(f"Períodos simulados: {metrics['periods']}")
        print(f"Taxa de ruptura: {metrics['stockout_rate']:.2%}")
        print(f"Estoque médio final: {metrics['avg_ending_inventory']:.2f}")
        print(f"Falta acumulada (unid): {metrics['total_shortage_units']:.2f}")
        print(f"Pedidos emitidos: {metrics['orders_placed']}")


if __name__ == "__main__":
    main()
