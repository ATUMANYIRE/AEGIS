"""Transportation network topology, distances, and cost structures for AEGIS."""

from dataclasses import dataclass, field

import numpy as np

from aegis.config import HOSPITALS, PRODUCT_CATEGORIES, WAREHOUSES


@dataclass(frozen=True)
class Coordinate:
    x_km: float
    y_km: float

    @property
    def x(self) -> float:
        return self.x_km

    @property
    def y(self) -> float:
        return self.y_km


@dataclass(frozen=True)
class NetworkParameters:
    """Network operational and economic parameters."""

    road_circuity_factor: float = 1.25
    vehicle_capacity_units: int = 2500
    fixed_vehicle_cost: float = 200.0
    base_route_cost: float = 150.0
    route_cost_per_km: float = 1.20
    max_route_capacity_units: int = 8000
    planning_horizon_days: int = 3

    # Product transport unit rates ($ / unit / km)
    product_unit_rates: dict[str, float] = field(
        default_factory=lambda: {
            "PPE": 0.018,
            "Sanitation": 0.024,
            "Medical_Utility": 0.015,
        }
    )

    # Base shortage penalties ($ / unmet unit)
    base_shortage_penalties: dict[str, float] = field(
        default_factory=lambda: {
            "PPE": 180.0,
            "Sanitation": 160.0,
            "Medical_Utility": 140.0,
        }
    )

    # Hospital tier penalty multipliers
    tier_penalty_multipliers: dict[str, float] = field(
        default_factory=lambda: {
            "Level_1_Trauma": 1.50,
            "Regional_Referral": 1.25,
            "Community": 1.00,
            "Specialty_Clinic": 0.85,
        }
    )

    # Daily warehouse dispatch throughput capacities (units/day)
    warehouse_dispatch_capacities: dict[str, int] = field(
        default_factory=lambda: {
            "W01": 25000,
            "W02": 16000,
            "W03": 16000,
        }
    )


class TransportationNetwork:
    """Deterministic transportation topology connecting warehouses to hospitals."""

    def __init__(self, params: NetworkParameters | None = None) -> None:
        self.params = params or NetworkParameters()
        self.warehouse_coords = self._build_warehouse_coordinates()
        self.hospital_coords = self._build_hospital_coordinates()
        self.distances_km = self._compute_distance_matrix()
        self.transport_costs = self._compute_transport_costs()
        self.fixed_route_costs = self._compute_fixed_route_costs()
        self.shortage_penalties = self._compute_shortage_penalties()

    @property
    def coordinates(self) -> dict[str, Coordinate]:
        """Combined spatial coordinates for all warehouses and hospitals."""
        return {**self.warehouse_coords, **self.hospital_coords}

    def _build_warehouse_coordinates(self) -> dict[str, Coordinate]:
        """Establish spatial coordinates for the 3 fulfillment hubs."""
        return {
            "W01": Coordinate(0.0, 0.0),  # Central Logistics Center
            "W02": Coordinate(0.0, 110.0),  # Northern Regional Depot
            "W03": Coordinate(0.0, -110.0),  # Southern Regional Depot
        }

    def _build_hospital_coordinates(self) -> dict[str, Coordinate]:
        """Generate deterministic, clustered spatial coordinates for 20 hospitals."""
        coords: dict[str, Coordinate] = {}
        # Deterministic radial positioning around assigned warehouse centroids
        # Angle step: 2 * pi / 7 ~ 0.897 rad
        for idx, h in enumerate(HOSPITALS):
            hub_coord = self.warehouse_coords[h.assigned_warehouse_id]
            # Offset based on hospital index and base lead time
            radius = 18.0 + (h.base_lead_time_days * 16.0) + (idx % 4) * 8.0
            angle = (idx * 0.94) % (2.0 * np.pi)
            x = hub_coord.x_km + radius * np.cos(angle)
            y = hub_coord.y_km + radius * np.sin(angle)
            coords[h.hospital_id] = Coordinate(round(x, 2), round(y, 2))
        return coords

    def _compute_distance_matrix(self) -> dict[tuple[str, str], float]:
        """Compute road network distance (km) between all warehouse-hospital pairs."""
        distances: dict[tuple[str, str], float] = {}
        for w in WAREHOUSES:
            w_coord = self.warehouse_coords[w.warehouse_id]
            for h in HOSPITALS:
                h_coord = self.hospital_coords[h.hospital_id]
                euclidean = np.hypot(w_coord.x_km - h_coord.x_km, w_coord.y_km - h_coord.y_km)
                road_dist = round(euclidean * self.params.road_circuity_factor, 1)
                distances[(w.warehouse_id, h.hospital_id)] = road_dist
        return distances

    def _compute_transport_costs(self) -> dict[tuple[str, str, str], float]:
        """Compute variable shipping cost ($/unit) for (w, h, c) triplets."""
        costs: dict[tuple[str, str, str], float] = {}
        for (w_id, h_id), dist in self.distances_km.items():
            for c in PRODUCT_CATEGORIES:
                rate = self.params.product_unit_rates[c.category_id]
                costs[(w_id, h_id, c.category_id)] = round(dist * rate, 4)
        return costs

    def _compute_fixed_route_costs(self) -> dict[tuple[str, str], float]:
        """Compute fixed activation cost ($) for establishing route (w, h)."""
        fixed_costs: dict[tuple[str, str], float] = {}
        for (w_id, h_id), dist in self.distances_km.items():
            cost = self.params.base_route_cost + self.params.route_cost_per_km * dist
            fixed_costs[(w_id, h_id)] = round(cost, 2)
        return fixed_costs

    def _compute_shortage_penalties(self) -> dict[tuple[str, str], float]:
        """Compute clinical shortage penalty ($/unmet unit) per (hospital, category)."""
        penalties: dict[tuple[str, str], float] = {}

        for h in HOSPITALS:
            tier_mult = self.params.tier_penalty_multipliers.get(h.tier, 1.0)
            for c in PRODUCT_CATEGORIES:
                base_pen = self.params.base_shortage_penalties[c.category_id]
                penalties[(h.hospital_id, c.category_id)] = round(base_pen * tier_mult, 2)
        return penalties

    def is_lead_time_eligible(self, warehouse_id: str, hospital_id: str) -> bool:
        """Check if delivery from warehouse to hospital meets planning horizon."""
        dist = self.distances_km.get((warehouse_id, hospital_id), 999.0)
        # Approximate delivery days: 1 day per 120 km + 1 day handling
        est_days = 1 + int(dist // 120)
        return est_days <= self.params.planning_horizon_days
