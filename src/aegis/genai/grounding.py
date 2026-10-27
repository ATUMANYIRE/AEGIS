"""Grounding validation, numerical consistency verification, and prompt-injection defense for GenAI."""

import re
from typing import Any

from aegis.genai.schema import DecisionContextRecord, GroundingAudit


class GroundingValidator:
    """Validates that GenAI explanations cite only verified numerical claims and maintain clinical boundaries."""

    INJECTION_PATTERNS = [
        re.compile(r"ignore\s+(all\s+)?(previous|above)\s+instructions", re.IGNORECASE),
        re.compile(r"system\s+prompt", re.IGNORECASE),
        re.compile(r"override\s+(all\s+)?constraints", re.IGNORECASE),
        re.compile(r"disregard\s+safety", re.IGNORECASE),
        re.compile(r"jailbreak", re.IGNORECASE),
        re.compile(r"pretend\s+you\s+are", re.IGNORECASE),
        re.compile(r"act\s+as\s+(an?\s+)?unrestricted", re.IGNORECASE),
        re.compile(r"simulate\s+admin", re.IGNORECASE),
        re.compile(r"bypass\s+governance", re.IGNORECASE),
    ]

    CLINICAL_VIOLATION_PATTERNS = [
        re.compile(r"\b(diagnos(e|is|ed))\b", re.IGNORECASE),
        re.compile(r"\b(prescribe|prescription|dosage|mg\/kg)\b", re.IGNORECASE),
        re.compile(r"\b(ventilator\s+withdrawal|triage\s+code\s+black)\b", re.IGNORECASE),
        re.compile(r"\b(patient\s+intubation|clinical\s+prognosis)\b", re.IGNORECASE),
    ]

    def __init__(self, numeric_tolerance: float = 0.05) -> None:
        self.numeric_tolerance = numeric_tolerance

    def sanitize_user_query(self, user_query: str | None) -> tuple[str, bool]:
        """Detect and neutralize prompt-injection attempts in user input."""
        if not user_query:
            return "", False

        cleaned = user_query.strip()
        detected = False
        for pattern in self.INJECTION_PATTERNS:
            if pattern.search(cleaned):
                detected = True
                cleaned = pattern.sub("[REDACTED_INJECTION_ATTEMPT]", cleaned)

        return cleaned, detected

    def check_clinical_boundaries(self, text: str) -> list[str]:
        """Verify that explanation does not issue clinical patient-care advice."""
        violations = []
        for pattern in self.CLINICAL_VIOLATION_PATTERNS:
            match = pattern.search(text)
            if match:
                violations.append(f"Forbidden clinical terminology detected: '{match.group(0)}'")
        return violations

    def extract_context_numbers(self, record: DecisionContextRecord) -> set[float]:
        """Extract all valid factual numbers present in the decision record."""
        numbers: set[float] = set()

        def add_num(val: Any) -> None:
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                numbers.add(round(float(val), 2))
                numbers.add(round(float(val), 1))
                numbers.add(round(float(val), 0))

        # Forecast
        add_num(record.forecast.point_forecast)
        add_num(record.forecast.p10_lower)
        add_num(record.forecast.p90_upper)
        add_num(record.forecast.prediction_interval_width)
        add_num(record.forecast.historical_wape_pct)

        # SHAP
        add_num(record.shap_base_value)
        for s in record.top_shap_contributions:
            add_num(s.feature_value)
            add_num(s.shap_value)

        # Optimization
        add_num(record.optimization.total_cost)
        add_num(record.optimization.transport_cost)
        add_num(record.optimization.route_activation_cost)
        add_num(record.optimization.vehicle_cost)
        add_num(record.optimization.shortage_penalty)
        add_num(record.optimization.service_coverage_pct)
        add_num(record.optimization.total_unmet_demand)
        add_num(record.optimization.facility_allocated_units)
        add_num(record.optimization.facility_fill_rate_pct)

        # Fairness
        add_num(record.fairness.min_fill_rate_pct)
        add_num(record.fairness.mean_fill_rate_pct)
        add_num(record.fairness.max_fill_rate_pct)
        add_num(record.fairness.disparity_ratio)
        add_num(record.fairness.trauma_tier_fill_rate_pct)
        add_num(record.fairness.community_tier_fill_rate_pct)
        add_num(record.fairness.specialty_tier_fill_rate_pct)

        # Scenario
        add_num(record.scenario_deltas.demand_surge_pct)
        add_num(record.scenario_deltas.stock_multiplier_pct)
        add_num(record.scenario_deltas.vehicle_capacity_units)
        add_num(record.scenario_deltas.min_service_coverage_target)
        add_num(record.scenario_deltas.shortage_penalty_multiplier)

        return numbers

    def validate_text(
        self,
        text: str,
        record: DecisionContextRecord,
        provider: str = "deterministic-fallback",
        latency_ms: float = 0.0,
        prompt_injection_detected: bool = False,
    ) -> GroundingAudit:
        """Audit candidate text for factual numerical grounding against decision context."""
        context_numbers = self.extract_context_numbers(record)

        # Extract numbers from text (e.g. 120, 45.6, 95%, $12,400)
        raw_num_matches = re.findall(r"[\$]?(\d+(?:,\d{3})*(?:\.\d+)?%?)", text)
        verified_claims: list[str] = []
        unverified_claims: list[str] = []

        # Standard non-statistical numbers to ignore (e.g. 1, 2, 7 for days of week, 80% for intervals, 2026 for year)
        ignorable_constants = {
            1.0,
            2.0,
            3.0,
            4.0,
            5.0,
            7.0,
            10.0,
            14.0,
            20.0,
            30.0,
            80.0,
            90.0,
            95.0,
            100.0,
            365.0,
            2026.0,
        }

        for match_str in raw_num_matches:
            clean_str = match_str.replace("$", "").replace("%", "").replace(",", "")
            try:
                val = float(clean_str)
            except ValueError:
                continue

            if val in ignorable_constants:
                continue

            # Check if val matches any number in context within tolerance
            is_match = False
            for c_val in context_numbers:
                if abs(val - c_val) <= max(1.0, abs(c_val) * self.numeric_tolerance):
                    is_match = True
                    verified_claims.append(f"{match_str} matches verified context ({c_val})")
                    break

            if not is_match:
                unverified_claims.append(f"Ungrounded number in text: {match_str} ({val})")

        # Check clinical boundaries
        clinical_violations = self.check_clinical_boundaries(text)
        unverified_claims.extend(clinical_violations)

        is_grounded = len(unverified_claims) == 0

        return GroundingAudit(
            is_grounded=is_grounded,
            verified_numerical_claims=verified_claims[:10],
            unverified_claims=unverified_claims,
            prompt_injection_detected=prompt_injection_detected,
            provider_used=provider,
            latency_ms=round(latency_ms, 2),
        )
