"""USSD Analytics Service — Sprint 76
Completion rates, drop-off points, avg session duration, funnel analysis
Connects to Kafka for session events, Redis for real-time counters
"""
import json, time, os, math
from http.server import HTTPServer, BaseHTTPRequestHandler
from collections import defaultdict
from threading import Lock

SERVICE_NAME = "ussd-analytics"
SERVICE_VERSION = "1.0.0"
DEFAULT_PORT = 9106

class USSDAnalytics:
    def __init__(self):
        self.lock = Lock()
        self.sessions = []
        self.step_counts = defaultdict(int)
        self.drop_off_points = defaultdict(int)
        self.completion_by_type = defaultdict(lambda: {"started": 0, "completed": 0})
        self.duration_samples = []
        self.carrier_stats = defaultdict(lambda: {"sessions": 0, "completed": 0, "total_duration": 0})
        self.region_stats = defaultdict(lambda: {"sessions": 0, "completed": 0})
        self.hourly_volume = defaultdict(int)

    def record_session(self, session):
        with self.lock:
            self.sessions.append(session)
            tx_type = session.get("type", "unknown")
            carrier = session.get("carrier", "unknown")
            region = session.get("region", "unknown")
            steps = session.get("steps", [])
            completed = session.get("completed", False)
            duration = session.get("durationMs", 0)
            self.completion_by_type[tx_type]["started"] += 1
            if completed:
                self.completion_by_type[tx_type]["completed"] += 1
            for step in steps:
                self.step_counts[step] += 1
            if not completed and steps:
                self.drop_off_points[steps[-1]] += 1
            self.duration_samples.append(duration)
            self.carrier_stats[carrier]["sessions"] += 1
            if completed:
                self.carrier_stats[carrier]["completed"] += 1
            self.carrier_stats[carrier]["total_duration"] += duration
            self.region_stats[region]["sessions"] += 1
            if completed:
                self.region_stats[region]["completed"] += 1
            hour = time.strftime("%Y-%m-%d %H:00", time.localtime(session.get("timestamp", time.time())))
            self.hourly_volume[hour] += 1

    def get_summary(self):
        with self.lock:
            total = len(self.sessions)
            completed = sum(1 for s in self.sessions if s.get("completed"))
            avg_duration = sum(self.duration_samples) / len(self.duration_samples) if self.duration_samples else 0
            return {
                "totalSessions": total,
                "completedSessions": completed,
                "completionRate": round(completed / total * 100, 1) if total > 0 else 0,
                "avgDurationMs": round(avg_duration),
                "dropOffPoints": dict(self.drop_off_points),
                "stepCounts": dict(self.step_counts),
                "completionByType": {k: {**v, "rate": round(v["completed"] / v["started"] * 100, 1) if v["started"] > 0 else 0} for k, v in self.completion_by_type.items()},
                "carrierStats": {k: {**v, "completionRate": round(v["completed"] / v["sessions"] * 100, 1) if v["sessions"] > 0 else 0, "avgDurationMs": round(v["total_duration"] / v["sessions"]) if v["sessions"] > 0 else 0} for k, v in self.carrier_stats.items()},
                "regionStats": {k: {**v, "completionRate": round(v["completed"] / v["sessions"] * 100, 1) if v["sessions"] > 0 else 0} for k, v in self.region_stats.items()},
                "hourlyVolume": dict(sorted(self.hourly_volume.items())[-24:]),
            }

analytics = USSDAnalytics()

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self._json({"service": SERVICE_NAME, "version": SERVICE_VERSION, "status": "healthy", "sessions": len(analytics.sessions)})
        elif self.path.startswith("/api/ussd-analytics/summary"):
            self._json(analytics.get_summary())
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/api/ussd-analytics/record":
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            analytics.record_session(body)
            self._json({"status": "recorded"})
        else:
            self.send_error(404)

    def _json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format, *args): pass

if __name__ == "__main__":
    port = int(os.environ.get("PORT", DEFAULT_PORT))
    print(f"[{SERVICE_NAME}] v{SERVICE_VERSION} listening on :{port}")
    HTTPServer(("", port), Handler).serve_forever()
