"""Heuristic and rule-based baseline supply allocation policies."""

import time

import numpy as np

from aegis.config import HOSPITALS, PRODUCT_CATEGORIES, WAREHOUSES
from aegis.optimization.schema import (
    FacilityShortage,
    FairnessDiagnostics,
    OptimizationResult,
    RouteDispatch,
    ShipmentAllocation,
)
from aegis.scenarios.network import TransportationNetwork


class ProportionalAllocationPolicy:
    """Allocates available warehouse inventory strictly in proportion to hospital demand."""

    def __init__(self, network: TransportationNetwork | None = None) -> None:
        self.network = network or TransportationNetwork()
        self.warehouses = [w.warehouse_id for w in WAREHOUSES]
        self.hospitals = [h.hospital_id for h in HOSPITALS]
        self.categories = [c.category_id for c in PRODUCT_CATEGORIES]

    def solve(
        self,
        demands: dict[tuple[str, str], float],
        warehouse_stock: dict[tuple[str, str], int],
        min_service_coverage: float = 0.0,
        realized_demand: dict[tuple[str, str], float] | None = None,
    ) -> OptimizationResult:
        """Execute proportional supply allocation under physical network constraints."""
        start_time = time.perf_counter()

        # Track remaining inventory and capacities
        rem_stock = warehouse_stock.copy()
        rem_dispatch = {
            w: self.network.params.warehouse_dispatch_capacities.get(w, 30000)
            for w in self.warehouses
        }
        rem_route_cap = {
            (w, h): self.network.params.max_route_capacity_units
            for w in self.warehouses
            for h in self.hospitals
        }

        alloc_matrix: dict[tuple[str, str, str], int] = {}
        hospital_received: dict[tuple[str, str], int] = {}

        # 1. Proportional allocation per category
        for c_id in self.categories:
            tot_cat_demand = sum(float(demands.get((h_id, c_id), 0.0)) for h_id in self.hospitals)
            tot_cat_stock = sum(rem_stock.get((w_id, c_id), 0) for w_id in self.warehouses)

            if tot_cat_demand <= 0 or tot_cat_stock <= 0:
                continue

            for h_id in self.hospitals:
                d = float(demands.get((h_id, c_id), 0.0))
                if d <= 0:
                    continue

                # Target proportional share
                share = d / tot_cat_demand
                target_alloc = int(np.floor(min(d, tot_cat_stock * share)))

                # Fulfill from nearest eligible warehouse with stock
                eligible_warehouses = [
                    w for w in self.warehouses if self.network.is_lead_time_eligible(w, h_id)
                ]
                # Sort warehouses by distance to hospital
                eligible_warehouses.sort(
                    key=lambda w: self.network.distances_km.get((w, h_id), 999.0)
                )

                needed = target_alloc
                for w_id in eligible_warehouses:
                    if needed <= 0:
                        break
                    avail_stock = rem_stock.get((w_id, c_id), 0)
                    avail_disp = rem_dispatch[w_id]
                    avail_route = rem_route_cap[(w_id, h_id)]

                    can_ship = min(needed, avail_stock, avail_disp, avail_route)
                    if can_ship > 0:
                        alloc_matrix[(w_id, h_id, c_id)] = can_ship
                        rem_stock[(w_id, c_id)] -= can_ship
                        rem_dispatch[w_id] -= can_ship
                        rem_route_cap[(w_id, h_id)] -= can_ship
                        needed -= can_ship
                        hospital_received[(h_id, c_id)] = (
                            hospital_received.get((h_id, c_id), 0) + can_ship
                        )

        runtime = round(time.perf_counter() - start_time, 4)
        return self._build_result(
            alloc_matrix=alloc_matrix,
            hospital_received=hospital_received,
            demands=demands,
            min_service_coverage=min_service_coverage,
            runtime=runtime,
            policy_name="Proportional_Allocation",
            realized_demand=realized_demand,
        )

    def _build_result(
        self,
        alloc_matrix: dict[tuple[str, str, str], int],
        hospital_received: dict[tuple[str, str], int],
        demands: dict[tuple[str, str], float],
        min_service_coverage: float,
        runtime: float,
        policy_name: str,
        realized_demand: dict[tuple[str, str], float] | None,
    ) -> OptimizationResult:
        """Construct standard OptimizationResult."""
        allocations: list[ShipmentAllocation] = []
        routes: list[RouteDispatch] = []
        shortages: list[FacilityShortage] = []

        total_trans_cost = 0.0
        total_route_cost = 0.0
        total_veh_cost = 0.0
        total_penalty = 0.0
        total_shipped = 0

        route_volumes: dict[tuple[str, str], int] = {}
        for (w_id, h_id, c_id), qty in alloc_matrix.items():
            if qty > 0:
                unit_c = self.network.transport_costs[(w_id, h_id, c_id)]
                cost = round(qty * unit_c, 2)
                allocations.append(
                    ShipmentAllocation(
                        warehouse_id=w_id,
                        hospital_id=h_id,
                        category_id=c_id,
                        quantity=qty,
                        unit_transport_cost=unit_c,
                        total_transport_cost=cost,
                    )
                )
                total_trans_cost += cost
                total_shipped += qty
                route_volumes[(w_id, h_id)] = route_volumes.get((w_id, h_id), 0) + qty

        for (w_id, h_id), vol in route_volumes.items():
            if vol > 0:
                r_cost = self.network.fixed_route_costs[(w_id, h_id)]
                v_count = int(np.ceil(vol / self.network.params.vehicle_capacity_units))
                v_cost = v_count * self.network.params.fixed_vehicle_cost
                total_route_cost += r_cost
                total_veh_cost += v_cost
                routes.append(
                    RouteDispatch(
                        warehouse_id=w_id,
                        hospital_id=h_id,
                        active=True,
                        vehicles_assigned=v_count,
                        total_volume_units=vol,
                        fixed_activation_cost=r_cost,
                        vehicle_cost=v_cost,
                    )
                )

        eval_demands = realized_demand if realized_demand is not None else demands
        total_unmet = 0.0
        hospital_fill_rates: list[float] = []

        for h_id in self.hospitals:
            h_tot_demand = 0.0
            h_tot_alloc = 0
            for c_id in self.categories:
                d = float(eval_demands.get((h_id, c_id), 0.0))
                alloc = hospital_received.get((h_id, c_id), 0)
                shortage = max(0.0, d - alloc)
                fill = min(1.0, alloc / d) if d > 0 else 1.0
                pen_rate = self.network.shortage_penalties[(h_id, c_id)]
                pen = round(shortage * pen_rate, 2)

                total_unmet += shortage
                total_penalty += pen
                h_tot_demand += d
                h_tot_alloc += alloc

                shortages.append(
                    FacilityShortage(
                        hospital_id=h_id,
                        category_id=c_id,
                        demand_units=round(d, 2),
                        allocated_units=alloc,
                        shortage_units=round(shortage, 2),
                        fill_rate=round(fill, 4),
                        shortage_penalty=pen,
                    )
                )

            h_fill = min(1.0, h_tot_alloc / h_tot_demand) if h_tot_demand > 0 else 1.0
            hospital_fill_rates.append(h_fill)

        worst_fill = float(np.min(hospital_fill_rates)) if hospital_fill_rates else 0.0
        mean_fill = float(np.mean(hospital_fill_rates)) if hospital_fill_rates else 0.0
        coverage_disp = (
            float(np.max(hospital_fill_rates) - np.min(hospital_fill_rates))
            if hospital_fill_rates
            else 0.0
        )

        is_fair = bool(worst_fill >= (min_service_coverage - 1e-4))
        fairness = FairnessDiagnostics(
            worst_facility_fill_rate=round(worst_fill, 4),
            mean_facility_fill_rate=round(mean_fill, 4),
            coverage_disparity=round(coverage_disp, 4),
            configured_min_coverage=min_service_coverage,
            is_fairness_satisfied=is_fair,
        )

        total_cost = round(total_trans_cost + total_route_cost + total_veh_cost + total_penalty, 2)
        status = "FEASIBLE" if is_fair else "INFEASIBLE"

        return OptimizationResult(
            policy=policy_name,
            status=status,
            solver_name="Heuristic_Proportional",
            total_cost=total_cost,
            transportation_cost=round(total_trans_cost, 2),
            fixed_route_cost=round(total_route_cost, 2),
            vehicle_cost=round(total_veh_cost, 2),
            shortage_penalty=round(total_penalty, 2),
            total_units_shipped=total_shipped,
            total_unmet_demand=round(total_unmet, 2),
            allocations=allocations,
            routes=routes,
            shortages=shortages,
            fairness=fairness,
            solver_runtime_sec=runtime,
            mip_gap=0.0,
            is_out_of_sample_evaluated=realized_demand is not None,
        )


class GreedyAllocationPolicy(ProportionalAllocationPolicy):
    """Greedy priority allocation prioritizing clinical criticality per unit shipping cost."""

    def solve(
        self,
        demands: dict[tuple[str, str], float],
        warehouse_stock: dict[tuple[str, str], int],
        min_service_coverage: float = 0.0,
        realized_demand: dict[tuple[str, str], float] | None = None,
    ) -> OptimizationResult:
        """Allocate inventory greedily by highest shortage penalty / shipping cost ratio."""
        start_time = time.perf_counter()

        rem_stock = warehouse_stock.copy()
        rem_dispatch = {
            w: self.network.params.warehouse_dispatch_capacities.get(w, 30000)
            for w in self.warehouses
        }
        rem_route_cap = {
            (w, h): self.network.params.max_route_capacity_units
            for w in self.warehouses
            for h in self.hospitals
        }

        alloc_matrix: dict[tuple[str, str, str], int] = {}
        hospital_received: dict[tuple[str, str], int] = {}
        rem_demand = demands.copy()

        # Build candidate supply decisions (w, h, c) and score them
        candidates = []
        for w_id in self.warehouses:
            for h_id in self.hospitals:
                if not self.network.is_lead_time_eligible(w_id, h_id):
                    continue
                for c_id in self.categories:
                    pen = self.network.shortage_penalties[(h_id, c_id)]
                    cost = self.network.transport_costs[(w_id, h_id, c_id)]
                    # Priority score: Higher penalty per dollar of shipping cost
                    score = pen / (cost + 1.0)
                    candidates.append((score, w_id, h_id, c_id))

        # Sort descending by priority score
        candidates.sort(key=lambda x: x[0], reverse=True)

        for _, w_id, h_id, c_id in candidates:
            d_rem = float(rem_demand.get((h_id, c_id), 0.0))
            if d_rem <= 0:
                continue

            stk = rem_stock.get((w_id, c_id), 0)
            disp = rem_dispatch[w_id]
            route_cap = rem_route_cap[(w_id, h_id)]

            can_ship = min(int(np.floor(d_rem)), stk, disp, route_cap)
            if can_ship > 0:
                alloc_matrix[(w_id, h_id, c_id)] = (
                    alloc_matrix.get((w_id, h_id, c_id), 0) + can_ship
                )
                rem_stock[(w_id, c_id)] -= can_ship
                rem_dispatch[w_id] -= can_ship
                rem_route_cap[(w_id, h_id)] -= can_ship
                rem_demand[(h_id, c_id)] = max(0.0, d_rem - can_ship)
                hospital_received[(h_id, c_id)] = hospital_received.get((h_id, c_id), 0) + can_ship

        runtime = round(time.perf_counter() - start_time, 4)
        return self._build_result(
            alloc_matrix=alloc_matrix,
            hospital_received=hospital_received,
            demands=demands,
            min_service_coverage=min_service_coverage,
            runtime=runtime,
            policy_name="Greedy_Priority",
            realized_demand=realized_demand,
        )
