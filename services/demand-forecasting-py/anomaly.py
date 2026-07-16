"""
Demand Anomaly Detection
Identifies unusual demand patterns for inventory planning.
Uses statistical methods (Z-score, IQR, rolling deviation).
"""

import math
from datetime import datetime


class AnomalyDetector:
    """Detects anomalies in demand time series using multiple methods."""

    def __init__(self, z_threshold: float = 2.5, iqr_multiplier: float = 1.5):
        self.z_threshold = z_threshold
        self.iqr_multiplier = iqr_multiplier

    def detect(self, data_points: list[dict]) -> list[dict]:
        """
        Detect anomalies in demand data.
        Each data_point: {"date": "2024-01-01", "quantity": 150}
        """
        if len(data_points) < 5:
            return []

        values = [float(dp.get("quantity", 0)) for dp in data_points]
        dates = [dp.get("date", "") for dp in data_points]

        anomalies = []

        # Method 1: Z-Score
        z_anomalies = self._z_score_detection(values)

        # Method 2: IQR
        iqr_anomalies = self._iqr_detection(values)

        # Method 3: Rolling deviation
        rolling_anomalies = self._rolling_deviation(values)

        # Combine: flag as anomaly if detected by 2+ methods
        for i in range(len(values)):
            methods_flagged = []
            if i in z_anomalies:
                methods_flagged.append("z_score")
            if i in iqr_anomalies:
                methods_flagged.append("iqr")
            if i in rolling_anomalies:
                methods_flagged.append("rolling_deviation")

            if len(methods_flagged) >= 2:
                mean = sum(values) / len(values)
                deviation = (values[i] - mean) / mean if mean > 0 else 0
                anomalies.append({
                    "date": dates[i] if i < len(dates) else None,
                    "value": values[i],
                    "expectedRange": {
                        "lower": round(mean - 2 * self._std_dev(values), 2),
                        "upper": round(mean + 2 * self._std_dev(values), 2),
                    },
                    "deviation": round(deviation, 4),
                    "severity": self._classify_severity(abs(deviation)),
                    "methods": methods_flagged,
                    "type": "spike" if values[i] > mean else "drop",
                })

        return anomalies

    def _z_score_detection(self, values: list[float]) -> set[int]:
        """Flag indices where Z-score exceeds threshold."""
        anomalies = set()
        mean = sum(values) / len(values)
        std = self._std_dev(values)
        if std == 0:
            return anomalies

        for i, val in enumerate(values):
            z = abs(val - mean) / std
            if z > self.z_threshold:
                anomalies.add(i)
        return anomalies

    def _iqr_detection(self, values: list[float]) -> set[int]:
        """Flag indices outside IQR bounds."""
        anomalies = set()
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        q1 = sorted_vals[n // 4]
        q3 = sorted_vals[3 * n // 4]
        iqr = q3 - q1

        lower = q1 - self.iqr_multiplier * iqr
        upper = q3 + self.iqr_multiplier * iqr

        for i, val in enumerate(values):
            if val < lower or val > upper:
                anomalies.add(i)
        return anomalies

    def _rolling_deviation(self, values: list[float], window: int = 7) -> set[int]:
        """Flag indices where value deviates from rolling average by >50%."""
        anomalies = set()
        for i in range(window, len(values)):
            window_vals = values[i - window : i]
            window_avg = sum(window_vals) / window
            if window_avg > 0:
                deviation = abs(values[i] - window_avg) / window_avg
                if deviation > 0.5:
                    anomalies.add(i)
        return anomalies

    def _std_dev(self, values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        return math.sqrt(variance)

    def _classify_severity(self, deviation: float) -> str:
        if deviation > 1.0:
            return "critical"
        elif deviation > 0.5:
            return "high"
        elif deviation > 0.25:
            return "medium"
        return "low"
