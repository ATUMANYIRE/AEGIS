"""Unit tests for transportation network topology and parameters."""

from aegis.config import HOSPITALS, PRODUCT_CATEGORIES, WAREHOUSES
from aegis.scenarios.network import NetworkParameters, TransportationNetwork


def test_network_dimensions() -> None:
    """Test network contains all 20 hospitals, 3 warehouses, and 3 products."""
    net = TransportationNetwork()
    assert len(net.warehouse_coords) == 3
    assert len(net.hospital_coords) == 20
    assert len(net.distances_km) == 3 * 20
    assert len(net.transport_costs) == 3 * 20 * 3
    assert len(net.fixed_route_costs) == 3 * 20
    assert len(net.shortage_penalties) == 20 * 3


def test_network_distances_positive() -> None:
    """Test all road distances are strictly positive and plausible."""
    net = TransportationNetwork()
    for (w_id, h_id), dist in net.distances_km.items():
        assert dist > 5.0, f"Distance between {w_id} and {h_id} is unrealistically short: {dist}"
        assert dist < 400.0, f"Distance between {w_id} and {h_id} exceeds regional radius: {dist}"


def test_shortage_penalties_tier_hierarchy() -> None:
    """Test trauma centers have higher shortage penalties than community clinics."""
    net = TransportationNetwork()
    # H01 is Level 1 Trauma, H11 is Community
    for c in PRODUCT_CATEGORIES:
        pen_trauma = net.shortage_penalties[("H01", c.category_id)]
        pen_comm = net.shortage_penalties[("H11", c.category_id)]
        assert pen_trauma > pen_comm, f"Trauma penalty should exceed community for {c.category_id}"


def test_lead_time_eligibility() -> None:
    """Test lead-time eligibility logic based on planning horizon."""
    net = TransportationNetwork(NetworkParameters(planning_horizon_days=2))
    # Close pairs should be eligible
    eligible_count = sum(
        1
        for w in WAREHOUSES
        for h in HOSPITALS
        if net.is_lead_time_eligible(w.warehouse_id, h.hospital_id)
    )
    assert eligible_count > 0
