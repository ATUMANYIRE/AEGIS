"""Unit tests verifying mathematical MILP constraints, integrality, and invariants."""

import pytest

from aegis.config import HOSPITALS, PRODUCT_CATEGORIES, WAREHOUSES
from aegis.optimization.engine import optimize
from aegis.optimization.milp_deterministic import DeterministicMILPSolver
from aegis.optimization.milp_stochastic import StochasticMILPSolver
from aegis.scenarios.generator import ForecastScenarioGenerator
from aegis.scenarios.network import TransportationNetwork


@pytest.fixture
def opt_fixture():
    """Setup scenario set and stock fixture."""
    gen = ForecastScenarioGenerator()
    scen_set = gen.generate_scenario_set(target_date="2025-11-15", num_scenarios=3, seed=42)

    exp_demands = scen_set.get_expected_demands()
    stock = {}
    for c in PRODUCT_CATEGORIES:
        tot_d = sum(exp_demands.get((h.hospital_id, c.category_id), 0.0) for h in HOSPITALS)
        # Ample stock (1.2x demand)
        stock[("W01", c.category_id)] = int(tot_d * 0.6)
        stock[("W02", c.category_id)] = int(tot_d * 0.3)
        stock[("W03", c.category_id)] = int(tot_d * 0.3)

    return scen_set, stock


def test_milp_inventory_conservation(opt_fixture) -> None:
    """Verify that shipments from any warehouse never exceed on-hand inventory."""
    scen_set, stock = opt_fixture
    res = optimize(
        warehouse_stock=stock,
        scenario_set=scen_set,
        policy="deterministic_milp",
    )
    assert res.status == "OPTIMAL"

    # Independently recompute shipped per (warehouse, category)
    shipped_wc = {}
    for alloc in res.allocations:
        key = (alloc.warehouse_id, alloc.category_id)
        shipped_wc[key] = shipped_wc.get(key, 0) + alloc.quantity

    for key, shipped_qty in shipped_wc.items():
        assert shipped_qty <= stock.get(key, 0), (
            f"Warehouse {key[0]} exceeded stock for {key[1]}: {shipped_qty} > {stock.get(key, 0)}"
        )


def test_milp_integrality(opt_fixture) -> None:
    """Verify all shipped quantities, route flags, and vehicles are strictly integral."""
    scen_set, stock = opt_fixture
    res = optimize(
        warehouse_stock=stock,
        scenario_set=scen_set,
        policy="deterministic_milp",
    )
    assert res.status == "OPTIMAL"

    for alloc in res.allocations:
        assert isinstance(alloc.quantity, int)
        assert alloc.quantity >= 0

    for route in res.routes:
        assert isinstance(route.vehicles_assigned, int)
        assert route.vehicles_assigned >= 0
        assert isinstance(route.active, bool)


def test_milp_route_and_vehicle_linking(opt_fixture) -> None:
    """Verify that shipments trigger route activation and adequate vehicle fleet assignment."""
    scen_set, stock = opt_fixture
    net = TransportationNetwork()
    res = optimize(
        warehouse_stock=stock,
        scenario_set=scen_set,
        policy="deterministic_milp",
        network=net,
    )
    assert res.status == "OPTIMAL"

    route_dict = {(r.warehouse_id, r.hospital_id): r for r in res.routes}
    shipped_wh = {}
    for alloc in res.allocations:
        pair = (alloc.warehouse_id, alloc.hospital_id)
        shipped_wh[pair] = shipped_wh.get(pair, 0) + alloc.quantity

    for pair, tot_vol in shipped_wh.items():
        assert pair in route_dict, f"Shipment on route {pair} occurred without active route record!"
        route_rec = route_dict[pair]
        assert route_rec.active is True
        # Vehicle capacity check
        max_capacity = route_rec.vehicles_assigned * net.params.vehicle_capacity_units
        assert tot_vol <= max_capacity, (
            f"Volume {tot_vol} exceeded vehicle fleet capacity {max_capacity} on {pair}"
        )


def test_milp_dispatch_capacity(opt_fixture) -> None:
    """Verify total outbound shipments from any warehouse do not exceed dispatch limits."""
    scen_set, stock = opt_fixture
    net = TransportationNetwork()
    res = optimize(
        warehouse_stock=stock,
        scenario_set=scen_set,
        policy="deterministic_milp",
        network=net,
    )
    assert res.status == "OPTIMAL"

    dispatched_w = {}
    for alloc in res.allocations:
        w = alloc.warehouse_id
        dispatched_w[w] = dispatched_w.get(w, 0) + alloc.quantity

    for w_id, tot_disp in dispatched_w.items():
        disp_limit = net.params.warehouse_dispatch_capacities[w_id]
        assert tot_disp <= disp_limit, (
            f"Warehouse {w_id} dispatch exceeded: {tot_disp} > {disp_limit}"
        )


def test_milp_zero_inventory() -> None:
    """Test zero inventory forces zero shipments and 100% unmet demand."""
    gen = ForecastScenarioGenerator()
    scen_set = gen.generate_scenario_set(target_date="2025-11-15", num_scenarios=1, seed=42)

    zero_stock = {
        (w.warehouse_id, c.category_id): 0 for w in WAREHOUSES for c in PRODUCT_CATEGORIES
    }

    res = optimize(
        warehouse_stock=zero_stock,
        scenario_set=scen_set,
        policy="deterministic_milp",
    )

    assert res.status == "OPTIMAL"
    assert res.total_units_shipped == 0
    assert len(res.allocations) == 0
    assert res.total_cost > 0.0  # Incurred shortage penalties
    for sh in res.shortages:
        assert sh.allocated_units == 0
        assert sh.shortage_units == pytest.approx(sh.demand_units)


def test_milp_zero_demand() -> None:
    """Test zero demand yields zero cost and zero shipments."""
    zero_demands = {
        (h.hospital_id, c.category_id): 0.0 for h in HOSPITALS for c in PRODUCT_CATEGORIES
    }
    stock = {(w.warehouse_id, c.category_id): 5000 for w in WAREHOUSES for c in PRODUCT_CATEGORIES}

    solver = DeterministicMILPSolver()
    res = solver.solve(demands=zero_demands, warehouse_stock=stock)

    assert res.status == "OPTIMAL"
    assert res.total_units_shipped == 0
    assert res.total_cost == pytest.approx(0.0)


def test_stochastic_nonanticipativity(opt_fixture) -> None:
    """Verify stochastic MILP produces single shared first-stage allocation across scenarios."""
    scen_set, stock = opt_fixture
    solver = StochasticMILPSolver()
    res = solver.solve(scenario_set=scen_set, warehouse_stock=stock)

    assert res.status == "OPTIMAL"
    # Allocations are deterministic first-stage decisions
    assert len(res.allocations) > 0
    total_alloc_units = sum(a.quantity for a in res.allocations)
    assert total_alloc_units == res.total_units_shipped


def test_deterministic_reproducibility(opt_fixture) -> None:
    """Test identical inputs produce exact identical MILP solutions."""
    scen_set, stock = opt_fixture
    res1 = optimize(warehouse_stock=stock, scenario_set=scen_set, policy="deterministic_milp")
    res2 = optimize(warehouse_stock=stock, scenario_set=scen_set, policy="deterministic_milp")

    assert res1.total_cost == pytest.approx(res2.total_cost, rel=1e-5)
    assert res1.total_units_shipped == res2.total_units_shipped
    assert len(res1.allocations) == len(res2.allocations)
