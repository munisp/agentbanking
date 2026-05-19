"""
USSD Session Replayer — Sprint 78
Keystroke-by-keystroke playback of USSD sessions for debugging and analytics
"""
import json
import time
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional

@dataclass
class USSDKeystroke:
    timestamp: float
    input: str
    screen_text: str
    menu_level: int
    response_time_ms: float

@dataclass
class USSDSession:
    session_id: str
    phone_number: str
    carrier: str
    service_code: str
    agent_id: Optional[str]
    started_at: float
    ended_at: Optional[float]
    status: str  # active, completed, timeout, error, dropped
    keystrokes: List[USSDKeystroke] = field(default_factory=list)
    total_duration_ms: float = 0
    drop_off_screen: Optional[str] = None
    completion_rate: float = 0.0

class SessionReplayer:
    def __init__(self):
        self.sessions: Dict[str, USSDSession] = {}
        self._seed_sessions()

    def _seed_sessions(self):
        # Seed realistic USSD sessions
        sessions = [
            self._create_session("SESS-001", "+2348012345678", "MTN_NG", "*384#", "AGT-001", "completed", [
                ("*384#", "Welcome to 54Link\n1. Cash In\n2. Cash Out\n3. Transfer\n4. Balance", 0, 450),
                ("1", "Cash In\nEnter Amount:", 1, 320),
                ("50000", "Confirm Cash In ₦50,000\n1. Confirm\n2. Cancel", 2, 280),
                ("1", "Transaction Successful!\nRef: TX-ABC123\nBalance: ₦150,000", 3, 1200),
            ]),
            self._create_session("SESS-002", "+2348099887766", "Airtel_NG", "*384#", "AGT-002", "dropped", [
                ("*384#", "Welcome to 54Link\n1. Cash In\n2. Cash Out\n3. Transfer\n4. Balance", 0, 450),
                ("2", "Cash Out\nEnter Amount:", 1, 380),
                ("100000", "Confirm Cash Out ₦100,000\n1. Confirm\n2. Cancel", 2, 290),
            ]),
            self._create_session("SESS-003", "+254712345678", "Safaricom_KE", "*384#", "AGT-003", "completed", [
                ("*384#", "Welcome to 54Link\n1. Cash In\n2. Cash Out\n3. Transfer\n4. Balance", 0, 520),
                ("3", "Transfer\nEnter Recipient Phone:", 1, 340),
                ("+254798765432", "Enter Amount:", 2, 300),
                ("5000", "Confirm Transfer KES 5,000 to +254798765432\n1. Confirm\n2. Cancel", 3, 260),
                ("1", "Transfer Successful!\nRef: TX-DEF456", 4, 980),
            ]),
            self._create_session("SESS-004", "+2348055555555", "Glo_NG", "*384#", None, "timeout", [
                ("*384#", "Welcome to 54Link\n1. Cash In\n2. Cash Out\n3. Transfer\n4. Balance", 0, 450),
                ("4", "Balance Check\nAgent Code:", 1, 350),
            ]),
            self._create_session("SESS-005", "+233201234567", "MTN_GH", "*384#", "AGT-005", "error", [
                ("*384#", "Welcome to 54Link\n1. Cash In\n2. Cash Out\n3. Transfer\n4. Balance", 0, 480),
                ("1", "Cash In\nEnter Amount:", 1, 310),
                ("abc", "Error: Invalid amount. Please enter a number.", 2, 150),
            ]),
        ]
        for s in sessions:
            self.sessions[s.session_id] = s

    def _create_session(self, session_id, phone, carrier, code, agent_id, status, keystrokes_data):
        base_time = time.time() - 3600
        keystrokes = []
        for i, (inp, screen, level, resp_ms) in enumerate(keystrokes_data):
            keystrokes.append(USSDKeystroke(
                timestamp=base_time + i * 5,
                input=inp,
                screen_text=screen,
                menu_level=level,
                response_time_ms=resp_ms,
            ))
        total_ms = sum(k.response_time_ms for k in keystrokes) + len(keystrokes) * 3000
        max_level = max(k.menu_level for k in keystrokes) if keystrokes else 0
        expected_levels = 4  # Typical complete flow
        completion = min(1.0, (max_level + 1) / expected_levels)
        drop_off = keystrokes[-1].screen_text if status in ("dropped", "timeout") else None
        return USSDSession(
            session_id=session_id,
            phone_number=phone,
            carrier=carrier,
            service_code=code,
            agent_id=agent_id,
            started_at=base_time,
            ended_at=base_time + total_ms / 1000 if status != "active" else None,
            status=status,
            keystrokes=keystrokes,
            total_duration_ms=total_ms,
            drop_off_screen=drop_off,
            completion_rate=completion,
        )

    def replay(self, session_id: str) -> Optional[List[Dict]]:
        session = self.sessions.get(session_id)
        if not session:
            return None
        return [
            {
                "step": i + 1,
                "timestamp": k.timestamp,
                "input": k.input,
                "screen": k.screen_text,
                "level": k.menu_level,
                "response_ms": k.response_time_ms,
            }
            for i, k in enumerate(session.keystrokes)
        ]

    def get_analytics(self) -> Dict:
        total = len(self.sessions)
        completed = sum(1 for s in self.sessions.values() if s.status == "completed")
        dropped = sum(1 for s in self.sessions.values() if s.status == "dropped")
        timeout = sum(1 for s in self.sessions.values() if s.status == "timeout")
        errors = sum(1 for s in self.sessions.values() if s.status == "error")
        avg_duration = sum(s.total_duration_ms for s in self.sessions.values()) / total if total > 0 else 0
        avg_completion = sum(s.completion_rate for s in self.sessions.values()) / total if total > 0 else 0
        return {
            "total_sessions": total,
            "completed": completed,
            "dropped": dropped,
            "timeout": timeout,
            "errors": errors,
            "completion_rate": round(avg_completion * 100, 1),
            "avg_duration_ms": round(avg_duration, 0),
            "drop_off_screens": [s.drop_off_screen for s in self.sessions.values() if s.drop_off_screen],
        }

def main():
    replayer = SessionReplayer()
    print(f"[ussd-session-replayer] Starting with {len(replayer.sessions)} sessions")
    analytics = replayer.get_analytics()
    print(f"  Completion rate: {analytics['completion_rate']}%")
    print(f"  Avg duration: {analytics['avg_duration_ms']}ms")
    print(f"  Dropped: {analytics['dropped']}, Timeout: {analytics['timeout']}, Errors: {analytics['errors']}")
    print("\n  Replaying SESS-001:")
    steps = replayer.replay("SESS-001")
    if steps:
        for step in steps:
            print(f"    Step {step['step']}: Input='{step['input']}' -> {step['screen'][:50]}... ({step['response_ms']}ms)")

if __name__ == "__main__":
    main()
