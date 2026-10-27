"""Two-stage Stochastic Mixed-Integer Linear Programming (MILP) supply allocation solver."""

import time

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import dok_matrix

from aegis.config import HOSPITALS, PRODUCT_CATEGORIES, WAREHOUSES
from aegis.optimization.schema import (
    FacilityShortage,
    FairnessDiagnostics,
    OptimizationResult,
    RouteDispatch,
    ShipmentAllocation,
)
from aegis.scenarios.generator import ScenarioSet
from aegis.scenarios.network import TransportationNetwork


class StochasticMILPSolver:
    """Two-stage stochastic MILP solver minimizing expected supply chain cost under demand uncertainty.

    Stage 1 (Here-and-now): Physical shipments x, route activation y, vehicle fleet v.
    Stage 2 (Recourse): Scenario-dependent hospital unmet demand shortages s_k.
    """

    def __init__(self, network: TransportationNetwork | None = None) -> None:
        self.network = network or TransportationNetwork()
        self.warehouses = [w.warehouse_id for w in WAREHOUSES]
        self.hospitals = [h.hospital_id for h in HOSPITALS]
        self.categories = [c.category_id for c in PRODUCT_CATEGORIES]

        self.W = len(self.warehouses)
        self.H = len(self.hospitals)
        self.C = len(self.categories)

        self.num_x = self.W * self.H * self.C
        self.num_y = self.W * self.H
        self.num_v = self.W * self.H
        self.first_stage_vars = self.num_x + self.num_y + self.num_v

    def _x_idx(self, w: int, h: int, c: int) -> int:
        return w * (self.H * self.C) + h * self.C + c

    def _y_idx(self, w: int, h: int) -> int:
        return self.num_x + w * self.H + h

    def _v_idx(self, w: int, h: int) -> int:
        return self.num_x + self.num_y + w * self.H + h

    def _s_idx(self, k: int, h: int, c: int) -> int:
        return self.first_stage_vars + k * (self.H * self.C) + h * self.C + c

    def solve(
        self,
        scenario_set: ScenarioSet,
        warehouse_stock: dict[tuple[str, str], int],
        min_service_coverage: float = 0.0,
        time_limit_sec: float = 30.0,
        mip_rel_gap: float = 0.01,
        realized_demand: dict[tuple[str, str], float] | None = None,
    ) -> OptimizationResult:
        """Formulate and solve two-stage stochastic MILP with shared first-stage decisions."""
        start_time = time.perf_counter()
        scenarios = scenario_set.scenarios
        K = len(scenarios)
        if K == 0:
            raise ValueError("ScenarioSet contains no scenarios.")

        total_vars = self.first_stage_vars + K * (self.H * self.C)

        # 1. Objective function c
        c_obj = np.zeros(total_vars, dtype=np.float64)

        # First stage costs (shipment, route, vehicles)
        for w_idx, w_id in enumerate(self.warehouses):
            for h_idx, h_id in enumerate(self.hospitals):
                for c_idx, c_id in enumerate(self.categories):
                    idx = self._x_idx(w_idx, h_idx, c_idx)
                    c_obj[idx] = self.network.transport_costs[(w_id, h_id, c_id)]

                y_idx = self._y_idx(w_idx, h_idx)
                c_obj[y_idx] = self.network.fixed_route_costs[(w_id, h_id)]

                v_idx = self._v_idx(w_idx, h_idx)
                c_obj[v_idx] = self.network.params.fixed_vehicle_cost

        # Second stage costs: probability-weighted shortage penalties
        for k_idx, sc in enumerate(scenarios):
            prob = float(sc.probability)
            for h_idx, h_id in enumerate(self.hospitals):
                for c_idx, c_id in enumerate(self.categories):
                    idx = self._s_idx(k_idx, h_idx, c_idx)
                    pen = self.network.shortage_penalties[(h_id, c_id)]
                    c_obj[idx] = prob * pen

        # 2. Variable bounds and integrality
        lb = np.zeros(total_vars, dtype=np.float64)
        ub = np.full(total_vars, np.inf, dtype=np.float64)
        integrality = np.zeros(total_vars, dtype=np.int32)

        # First stage x: non-negative integer
        for w_idx, w_id in enumerate(self.warehouses):
            for h_idx, h_id in enumerate(self.hospitals):
                eligible = self.network.is_lead_time_eligible(w_id, h_id)
                for c_idx, c_id in enumerate(self.categories):
                    idx = self._x_idx(w_idx, h_idx, c_idx)
                    integrality[idx] = 1
                    if not eligible:
                        ub[idx] = 0.0
                    else:
                        stk = warehouse_stock.get((w_id, c_id), 0)
                        ub[idx] = max(0.0, float(stk))

        # First stage y: binary
        for w_idx, w_id in enumerate(self.warehouses):
            for h_idx, h_id in enumerate(self.hospitals):
                idx = self._y_idx(w_idx, h_idx)
                integrality[idx] = 1
                ub[idx] = 1.0 if self.network.is_lead_time_eligible(w_id, h_id) else 0.0

        # First stage v: integer
        max_veh = (
            int(
                np.ceil(
                    self.network.params.max_route_capacity_units
                    / self.network.params.vehicle_capacity_units
                )
            )
            + 1
        )
        for w_idx, w_id in enumerate(self.warehouses):
            for h_idx, h_id in enumerate(self.hospitals):
                idx = self._v_idx(w_idx, h_idx)
                integrality[idx] = 1
                ub[idx] = float(max_veh) if self.network.is_lead_time_eligible(w_id, h_id) else 0.0

        # Second stage s_k: non-negative continuous
        for k_idx, sc in enumerate(scenarios):
            for h_idx, h_id in enumerate(self.hospitals):
                for c_idx, c_id in enumerate(self.categories):
                    idx = self._s_idx(k_idx, h_idx, c_idx)
                    integrality[idx] = 0
                    ub[idx] = max(0.0, float(sc.demands.get((h_id, c_id), 0.0)))

        # 3. Constraints
        rows = []
        b_l_list = []
        b_u_list = []

        # Constraint set 1: Warehouse stock capacity (W * C constraints)
        for w_idx, w_id in enumerate(self.warehouses):
            for c_idx, c_id in enumerate(self.categories):
                row: dict[int, float] = {}
                for h_idx in range(self.H):
                    row[self._x_idx(w_idx, h_idx, c_idx)] = 1.0
                rows.append(row)
                b_l_list.append(-np.inf)
                b_u_list.append(float(warehouse_stock.get((w_id, c_id), 0)))

        # Constraint set 2: Vehicle linking (W * H constraints)
        v_cap = float(self.network.params.vehicle_capacity_units)
        for w_idx in range(self.W):
            for h_idx in range(self.H):
                row = {}
                for c_idx in range(self.C):
                    row[self._x_idx(w_idx, h_idx, c_idx)] = 1.0
                row[self._v_idx(w_idx, h_idx)] = -v_cap
                rows.append(row)
                b_l_list.append(-np.inf)
                b_u_list.append(0.0)

        # Constraint set 3: Route activation linking (W * H constraints)
        c_route = float(self.network.params.max_route_capacity_units)
        for w_idx in range(self.W):
            for h_idx in range(self.H):
                row1 = {
                    self._v_idx(w_idx, h_idx): 1.0,
                    self._y_idx(w_idx, h_idx): -float(max_veh),
                }
                rows.append(row1)
                b_l_list.append(-np.inf)
                b_u_list.append(0.0)

                row2 = {}
                for c_idx in range(self.C):
                    row2[self._x_idx(w_idx, h_idx, c_idx)] = 1.0
                row2[self._y_idx(w_idx, h_idx)] = -c_route
                rows.append(row2)
                b_l_list.append(-np.inf)
                b_u_list.append(0.0)

        # Constraint set 4: Warehouse dispatch throughput (W constraints)
        for w_idx, w_id in enumerate(self.warehouses):
            disp_cap = float(self.network.params.warehouse_dispatch_capacities.get(w_id, 30000))
            row = {}
            for h_idx in range(self.H):
                for c_idx in range(self.C):
                    row[self._x_idx(w_idx, h_idx, c_idx)] = 1.0
            rows.append(row)
            b_l_list.append(-np.inf)
            b_u_list.append(disp_cap)

        # Constraint set 5: Second-stage scenario demand balances (K * H * C constraints)
        # sum_w x_whc + s_whck >= d_hck (recourse shortage)
        for k_idx, sc in enumerate(scenarios):
            for h_idx, h_id in enumerate(self.hospitals):
                for c_idx, c_id in enumerate(self.categories):
                    row = {}
                    for w_idx in range(self.W):
                        row[self._x_idx(w_idx, h_idx, c_idx)] = 1.0
                    row[self._s_idx(k_idx, h_idx, c_idx)] = 1.0
                    rows.append(row)
                    d_val = float(sc.demands.get((h_id, c_id), 0.0))
                    b_l_list.append(d_val)
                    b_u_list.append(np.inf)

        # Constraint set 6: Minimum service coverage fairness (H constraints)
        # sum_{w, c} x_whc >= alpha_min * sum_c E[d_hc]
        expected_demands = scenario_set.get_expected_demands()
        if min_service_coverage > 0.0:
            for h_idx, h_id in enumerate(self.hospitals):
                exp_tot_d = sum(
                    float(expected_demands.get((h_id, c_id), 0.0)) for c_id in self.categories
                )
                min_req = np.ceil(min_service_coverage * exp_tot_d)
                row = {}
                for w_idx in range(self.W):
                    for c_idx in range(self.C):
                        row[self._x_idx(w_idx, h_idx, c_idx)] = 1.0
                rows.append(row)
                b_l_list.append(min_req)
                b_u_list.append(np.inf)

        # Build sparse matrix
        num_cons = len(rows)
        A = dok_matrix((num_cons, total_vars), dtype=np.float64)
        for r_idx, r_dict in enumerate(rows):
            for c_idx, val in r_dict.items():
                A[r_idx, c_idx] = val

        constraints = LinearConstraint(A.tocsc(), b_l_list, b_u_list)
        bounds = Bounds(lb, ub)

        options = {
            "time_limit": time_limit_sec,
            "mip_rel_gap": mip_rel_gap,
            "disp": False,
        }

        # 4. Solve via SciPy HiGHS
        res = milp(
            c=c_obj,
            constraints=constraints,
            integrality=integrality,
            bounds=bounds,
            options=options,
        )
        runtime = round(time.perf_counter() - start_time, 4)

        status_map = {0: "OPTIMAL", 1: "TIME_LIMIT", 2: "INFEASIBLE", 3: "FEASIBLE"}
        res_status = status_map.get(res.status, "ERROR")

        if not res.success and res.status == 2:
            return self._build_infeasible_result(
                expected_demands=expected_demands,
                warehouse_stock=warehouse_stock,
                min_service_coverage=min_service_coverage,
                runtime=runtime,
            )

        z_sol = res.x if res.x is not None else np.zeros(total_vars)

        return self._extract_solution(
            z=z_sol,
            scenario_set=scenario_set,
            warehouse_stock=warehouse_stock,
            min_service_coverage=min_service_coverage,
            status=res_status,
            runtime=runtime,
            realized_demand=realized_demand,
        )

    def _extract_solution(
        self,
        z: np.ndarray,
        scenario_set: ScenarioSet,
        warehouse_stock: dict[tuple[str, str], int],
        min_service_coverage: float,
        status: str,
        runtime: float,
        realized_demand: dict[tuple[str, str], float] | None = None,
    ) -> OptimizationResult:
        """Extract first-stage allocation and compute performance metrics."""
        allocations: list[ShipmentAllocation] = []
        routes: list[RouteDispatch] = []
        shortages: list[FacilityShortage] = []

        total_trans_cost = 0.0
        total_route_cost = 0.0
        total_veh_cost = 0.0
        total_shipped = 0

        # Shipped quantities per (h, c)
        hospital_received: dict[tuple[str, str], int] = {}

        for w_idx, w_id in enumerate(self.warehouses):
            for h_idx, h_id in enumerate(self.hospitals):
                route_qty = 0
                for c_idx, c_id in enumerate(self.categories):
                    qty = int(round(z[self._x_idx(w_idx, h_idx, c_idx)]))
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
                        route_qty += qty
                        hospital_received[(h_id, c_id)] = (
                            hospital_received.get((h_id, c_id), 0) + qty
                        )

                y_val = bool(round(z[self._y_idx(w_idx, h_idx)]) > 0.5 or route_qty > 0)
                v_val = int(round(z[self._v_idx(w_idx, h_idx)]))
                if route_qty > 0 and v_val == 0:
                    v_val = int(np.ceil(route_qty / self.network.params.vehicle_capacity_units))

                if y_val or route_qty > 0:
                    r_cost = self.network.fixed_route_costs[(w_id, h_id)]
                    v_cost = v_val * self.network.params.fixed_vehicle_cost
                    total_route_cost += r_cost
                    total_veh_cost += v_cost
                    routes.append(
                        RouteDispatch(
                            warehouse_id=w_id,
                            hospital_id=h_id,
                            active=True,
                            vehicles_assigned=v_val,
                            total_volume_units=route_qty,
                            fixed_activation_cost=r_cost,
                            vehicle_cost=v_cost,
                        )
                    )

        # Evaluation against out-of-sample realized demand or expected scenario demands
        eval_demands = (
            realized_demand if realized_demand is not None else scenario_set.get_expected_demands()
        )

        total_penalty = 0.0
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

        fairness = FairnessDiagnostics(
            worst_facility_fill_rate=round(worst_fill, 4),
            mean_facility_fill_rate=round(mean_fill, 4),
            coverage_disparity=round(coverage_disp, 4),
            configured_min_coverage=min_service_coverage,
            is_fairness_satisfied=bool(worst_fill >= (min_service_coverage - 1e-4)),
        )

        total_cost = round(total_trans_cost + total_route_cost + total_veh_cost + total_penalty, 2)

        return OptimizationResult(
            policy="Stochastic_MILP",
            status="OPTIMAL" if status == "OPTIMAL" else status,  # type: ignore[arg-type]
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

    def _build_infeasible_result(
        self,
        expected_demands: dict[tuple[str, str], float],
        warehouse_stock: dict[tuple[str, str], int],
        min_service_coverage: float,
        runtime: float,
    ) -> OptimizationResult:
        """Construct diagnostic result when stochastic MILP is infeasible."""
        total_d = sum(expected_demands.values())
        total_s = sum(warehouse_stock.values())
        deficit = max(0.0, min_service_coverage * total_d - total_s)

        fairness = FairnessDiagnostics(
            worst_facility_fill_rate=0.0,
            mean_facility_fill_rate=0.0,
            coverage_disparity=0.0,
            configured_min_coverage=min_service_coverage,
            is_fairness_satisfied=False,
            total_inventory_deficit=round(deficit, 2),
            relaxation_summary=f"Infeasible service coverage target {min_service_coverage:.1%}. Total stock {total_s} < required {min_service_coverage * total_d:.1f}.",
        )

        return OptimizationResult(
            policy="Stochastic_MILP",
            status="INFEASIBLE",
            total_cost=float("inf"),
            transportation_cost=0.0,
            fixed_route_cost=0.0,
            vehicle_cost=0.0,
            shortage_penalty=float("inf"),
            total_units_shipped=0,
            total_unmet_demand=round(total_d, 2),
            allocations=[],
            routes=[],
            shortages=[],
            fairness=fairness,
            solver_runtime_sec=runtime,
            mip_gap=1.0,
        )
