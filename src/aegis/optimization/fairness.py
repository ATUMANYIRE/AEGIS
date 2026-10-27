"""Fairness analysis, infeasibility diagnosis, and constraint relaxation engine."""

from aegis.config import HOSPITALS, PRODUCT_CATEGORIES, WAREHOUSES
from aegis.optimization.schema import FairnessDiagnostics
from aegis.scenarios.network import TransportationNetwork


class FairnessRelaxationAnalyzer:
    """Diagnoses infeasibility and computes mathematically sound fairness relaxations."""

    def __init__(self, network: TransportationNetwork | None = None) -> None:
        self.network = network or TransportationNetwork()
        self.warehouses = [w.warehouse_id for w in WAREHOUSES]
        self.hospitals = [h.hospital_id for h in HOSPITALS]
        self.categories = [c.category_id for c in PRODUCT_CATEGORIES]

    def analyze_relaxation(
        self,
        demands: dict[tuple[str, str], float],
        warehouse_stock: dict[tuple[str, str], int],
        target_min_coverage: float,
    ) -> FairnessDiagnostics:
        """Analyze why a target minimum service coverage is infeasible and compute maximum achievable coverage.

        Parameters
        ----------
        demands : dict[tuple[str, str], float]
            Expected demand per (hospital, category).
        warehouse_stock : dict[tuple[str, str], int]
            Available inventory per (warehouse, category).
        target_min_coverage : float
            Requested minimum fill rate per hospital (e.g. 0.85).

        Returns
        -------
        FairnessDiagnostics
            Diagnostic report with maximum feasible coverage and resource deficit analysis.
        """
        tot_demand = sum(demands.values())
        tot_stock = sum(warehouse_stock.values())

        # 1. Physical global bounds
        # Overall inventory capacity bound
        stock_ratio = tot_stock / tot_demand if tot_demand > 0 else 1.0

        # Category-level inventory bounds
        cat_deficits: dict[str, float] = {}
        max_cat_coverages: list[float] = []
        for c in self.categories:
            c_dem = sum(float(demands.get((h, c), 0.0)) for h in self.hospitals)
            c_stk = sum(warehouse_stock.get((w, c), 0) for w in self.warehouses)
            ratio = c_stk / c_dem if c_dem > 0 else 1.0
            max_cat_coverages.append(ratio)
            deficit = max(0.0, target_min_coverage * c_dem - c_stk)
            if deficit > 0:
                cat_deficits[c] = round(deficit, 1)

        # Warehouse dispatch throughput bound
        tot_dispatch = sum(
            self.network.params.warehouse_dispatch_capacities.get(w, 30000) for w in self.warehouses
        )
        dispatch_ratio = tot_dispatch / tot_demand if tot_demand > 0 else 1.0

        # Upper bound on achievable uniform coverage
        max_achievable = min(
            1.0, stock_ratio, dispatch_ratio, min(max_cat_coverages) if max_cat_coverages else 1.0
        )
        max_feasible_alpha = max(0.0, min(max_achievable, 1.0))

        # Identify bottleneck warehouses
        bottlenecks = []
        for w in self.warehouses:
            w_stk = sum(warehouse_stock.get((w, c), 0) for c in self.categories)
            w_disp = self.network.params.warehouse_dispatch_capacities.get(w, 30000)
            if w_stk > w_disp:
                bottlenecks.append(w)

        total_deficit = max(0.0, target_min_coverage * tot_demand - tot_stock)
        is_feasible = bool(target_min_coverage <= max_feasible_alpha + 1e-4)

        if not is_feasible:
            summary = (
                f"Requested minimum service coverage {target_min_coverage:.1%} is mathematically infeasible. "
                f"Maximum achievable equitable coverage is {max_feasible_alpha:.1%}. "
                f"Total inventory deficit: {total_deficit:.1f} units. "
            )
            if cat_deficits:
                summary += f"Deficits by product: {cat_deficits}."
        else:
            summary = f"Configured fairness target {target_min_coverage:.1%} is feasible (max achievable {max_feasible_alpha:.1%})."

        return FairnessDiagnostics(
            worst_facility_fill_rate=0.0,
            mean_facility_fill_rate=0.0,
            coverage_disparity=0.0,
            configured_min_coverage=target_min_coverage,
            is_fairness_satisfied=is_feasible,
            max_feasible_coverage=round(max_feasible_alpha, 4),
            bottleneck_warehouses=bottlenecks,
            total_inventory_deficit=round(total_deficit, 2),
            relaxation_summary=summary,
        )
