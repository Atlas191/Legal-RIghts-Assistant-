"""Unit tests for the FastAPI layer (api.py and api_schemas.py).
Run:  python tests/test_api.py
Exit code 0 = all pass, 1 = at least one failure.
"""
import io
import logging
import os
import sys
from unittest.mock import patch

# Ensure project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["WARM_OLLAMA"] = "0"

from fastapi.testclient import TestClient

from schemas import Turn, Source, Forum, RoadmapAction, RoadmapStep, AskResult
import api


# --- Fake Pipeline for offline testing ---
class FakePipeline:
    def __init__(self):
        self.last_query = None
        self.last_history = None
        self.last_response_lang = None
        self.search = None
        self.raise_exc = None
        self.return_off_topic = False

    def ask(self, query: str, history: list[Turn] | None = None, response_lang: str = "auto") -> AskResult:
        if self.raise_exc:
            raise self.raise_exc
        self.last_query = query
        self.last_history = history
        self.last_response_lang = response_lang

        if self.return_off_topic:
            return AskResult(
                off_topic=True,
                answer="This situation appears to be outside women's legal rights.",
                verified=False,
                fallback=False,
                sources=[],
                disclaimer="This information is for guidance only...",
                resolved_query=query,
                cited_source_ids=[],
                routing=[],
                needs_info=[],
                roadmap=[],
            )

        return AskResult(
            off_topic=False,
            answer="Under Section 354 IPC / BNS 74 [S1], assault or criminal force to woman with intent to outrage modesty is punishable.",
            verified=True,
            fallback=False,
            sources=[
                Source(
                    id="bns:74",
                    heading="Section 74 — Assault or use of criminal force to woman with intent to outrage her modesty",
                    act="Bharatiya Nyaya Sanhita, 2023",
                    section="Section 74",
                    source_file="bns_2023.md",
                    text="Whoever assaults or uses criminal force to any woman...",
                    formerly_ipc="354",
                )
            ],
            disclaimer="This information is for guidance only...",
            resolved_query=query,
            cited_source_ids=["bns:74"],
            routing=[
                Forum(
                    name="Internal Complaints Committee (ICC)",
                    why="Workplace with 10+ employees",
                    time_limit="3 months",
                    kb_ref="posh_handbook",
                    category="institutional",
                )
            ],
            needs_info=[],
            roadmap=[
                RoadmapStep(
                    step=1,
                    kind="immediate",
                    title="Immediate Steps",
                    actions=[
                        RoadmapAction(
                            text="Preserve evidence and dates",
                            basis="general_guidance",
                        )
                    ],
                )
            ],
            detected_lang="en",
            response_lang="en",
        )


fake_pipe = FakePipeline()
api._pipe = lambda: fake_pipe
client = TestClient(api.app)


# --- Test Cases ---
def test_1_health():
    resp = client.get("/api/health")
    if resp.status_code != 200:
        return False
    data = resp.json()
    keys = {"status", "kb_sections", "kb_chunks", "ollama_reachable", "answer_translation"}
    if not keys.issubset(data.keys()):
        return False
    if data["kb_sections"] <= 0 or data["kb_chunks"] <= 0:
        return False
    return True


def test_2_examples():
    resp = client.get("/api/examples")
    if resp.status_code != 200:
        return False
    data = resp.json()
    examples = data.get("examples", [])
    if len(examples) != 6:
        return False
    if not data.get("disclaimer"):
        return False
    return True


def test_3_ask_valid():
    fake_pipe.raise_exc = None
    fake_pipe.return_off_topic = False
    resp = client.post("/api/ask", json={"query": "my boss keeps touching me at work"})
    if resp.status_code != 200:
        return False
    data = resp.json()
    for field in ["session_id", "sources", "routing", "roadmap", "disclaimer"]:
        if field not in data:
            return False
    if not data["session_id"] or not data["sources"]:
        return False
    return True


def test_4_ask_validation():
    resp1 = client.post("/api/ask", json={"query": ""})
    if resp1.status_code != 422:
        return False
    resp2 = client.post("/api/ask", json={"query": "a" * 1001})
    if resp2.status_code != 422:
        return False
    return True


def test_5_session_continuity():
    fake_pipe.raise_exc = None
    fake_pipe.return_off_topic = False
    resp1 = client.post("/api/ask", json={"query": "my boss keeps touching me at work"})
    if resp1.status_code != 200:
        return False
    sid = resp1.json()["session_id"]

    resp2 = client.post("/api/ask", json={"query": "we are 40 people", "session_id": sid})
    if resp2.status_code != 200:
        return False
    if fake_pipe.last_history is None or len(fake_pipe.last_history) != 2:
        return False
    if fake_pipe.last_history[0].text != "my boss keeps touching me at work":
        return False

    new_sid = "test_unknown_session_123"
    resp3 = client.post("/api/ask", json={"query": "first query in new session", "session_id": new_sid})
    if resp3.status_code != 200:
        return False
    if resp3.json()["session_id"] != new_sid:
        return False

    resp4 = client.post("/api/ask", json={"query": "follow up in new session", "session_id": new_sid})
    if resp4.status_code != 200:
        return False
    if fake_pipe.last_history is None or len(fake_pipe.last_history) != 2:
        return False
    if fake_pipe.last_history[0].text != "first query in new session":
        return False
    return True


def test_6_off_topic_not_in_history():
    fake_pipe.raise_exc = None
    fake_pipe.return_off_topic = True
    resp = client.post("/api/ask", json={"query": "how do i open a bank account"})
    if resp.status_code != 200:
        return False
    sid = resp.json()["session_id"]
    turns = api.get_session_turns(sid)
    if turns is not None and len(turns) > 0:
        return False
    return True


def test_7_delete_session():
    fake_pipe.raise_exc = None
    fake_pipe.return_off_topic = False
    resp1 = client.post("/api/ask", json={"query": "my husband threw me out"})
    sid = resp1.json()["session_id"]
    del_resp1 = client.delete(f"/api/session/{sid}")
    if del_resp1.status_code != 200 or del_resp1.json() != {"deleted": True}:
        return False
    del_resp2 = client.delete(f"/api/session/{sid}")
    if del_resp2.status_code != 200 or del_resp2.json() != {"deleted": False}:
        return False
    return True


def test_8_error_handling():
    fake_pipe.return_off_topic = False
    fake_pipe.raise_exc = ValueError("Invalid statutory reference")
    resp_val = client.post("/api/ask", json={"query": "test query"})
    if resp_val.status_code != 422 or "Invalid statutory reference" not in resp_val.text:
        return False

    fake_pipe.raise_exc = RuntimeError("secret text that must not leak")
    resp_err = client.post("/api/ask", json={"query": "test query"})
    fake_pipe.raise_exc = None
    if resp_err.status_code != 500:
        return False
    if "secret text that must not leak" in resp_err.text:
        return False
    if resp_err.json().get("detail") != "Something went wrong. Please try again.":
        return False
    return True


def test_9_draft():
    narrative = "On 12 March 2026 my manager touched me in the office cabin."
    resp1 = client.post("/api/draft", json={"narrative": narrative})
    if resp1.status_code != 200:
        return False
    data1 = resp1.json()
    if not data1.get("missing_fields"):
        return False
    if narrative not in data1.get("body", ""):
        return False

    resp2 = client.post("/api/draft", json={"narrative": ""})
    if resp2.status_code != 422:
        return False
    return True


def test_10_cors():
    resp1 = client.get("/api/health", headers={"Origin": "http://localhost:3000"})
    if resp1.headers.get("access-control-allow-origin") != "http://localhost:3000":
        return False
    resp2 = client.get("/api/health", headers={"Origin": "http://evil.example"})
    if "access-control-allow-origin" in resp2.headers:
        return False
    return True


def test_11_logging_privacy():
    fake_pipe.raise_exc = None
    fake_pipe.return_off_topic = False
    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)

    loggers = [logging.getLogger("api"), logging.getLogger("pipeline"), logging.getLogger("draft"), logging.getLogger()]
    for l in loggers:
        l.addHandler(handler)

    secret_token = "ZZZ_SECRET_TOKEN_123"
    resp_ask = client.post("/api/ask", json={"query": f"Help with {secret_token} situation"})
    answer_text = resp_ask.json().get("answer", "")

    client.post("/api/draft", json={"narrative": f"Incident with {secret_token} occurred yesterday."})

    for l in loggers:
        l.removeHandler(handler)

    all_logs = log_capture.getvalue()
    if secret_token in all_logs:
        return False
    if answer_text and answer_text in all_logs:
        return False
    return True


def test_12_busy_semaphore():
    fake_pipe.raise_exc = None
    fake_pipe.return_off_topic = False
    with patch.object(api._ask_semaphore, "acquire", return_value=False):
        resp = client.post("/api/ask", json={"query": "my boss touched me"})
        if resp.status_code != 503:
            return False
        if resp.json().get("detail") != "The assistant is busy, please try again in a moment.":
            return False
    return True


def test_13_openapi():
    resp = client.get("/openapi.json")
    if resp.status_code != 200:
        return False
    paths = resp.json().get("paths", {})
    required_paths = [
        "/api/health",
        "/api/examples",
        "/api/ask",
        "/api/draft",
        "/api/session/{session_id}",
    ]
    for p in required_paths:
        if p not in paths:
            return False
    return True


TESTS = [
    ("1. GET /api/health returns 200 with kb_sections > 0 and the keys of HealthResponse", test_1_health),
    ("2. GET /api/examples returns the 6 examples and the disclaimer", test_2_examples),
    ("3. POST /api/ask with a valid query returns 200, includes session_id, sources, routing, roadmap, disclaimer", test_3_ask_valid),
    ("4. POST /api/ask with an empty query returns 422, and a 1001-character query returns 422", test_4_ask_validation),
    ("5. a second call with the returned session_id passes stored history, unknown session starts new session", test_5_session_continuity),
    ("6. an off-topic result is NOT added to session history", test_6_off_topic_not_in_history),
    ("7. DELETE /api/session/{id} removes it (deleted true, then false)", test_7_delete_session),
    ("8. pipeline ValueError gives 422; RuntimeError gives 500 without leaking exception text", test_8_error_handling),
    ("9. POST /api/draft with narrative returns 200 with verbatim body; empty narrative gives 422", test_9_draft),
    ("10. CORS: localhost gets access-control-allow-origin; evil.example does not", test_10_cors),
    ("11. LOGGING PRIVACY: secret token and answer text never appear in logs", test_11_logging_privacy),
    ("12. busy path: semaphore timeout returns 503", test_12_busy_semaphore),
    ("13. OpenAPI: GET /openapi.json returns 200 and includes all endpoints", test_13_openapi),
]


def run():
    passed = 0
    failed = 0

    for name, fn in TESTS:
        try:
            ok = fn()
            if ok:
                passed += 1
                print(f"  [PASS] {name}")
            else:
                failed += 1
                print(f"  [FAIL] {name}")
        except Exception as e:
            failed += 1
            print(f"  [FAIL] {name} — {type(e).__name__}: {e}")

    print(f"\n{passed}/{passed + failed} passed.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
