"""回合出口的验收：SSE 帧的顺序、序号、身份与幂等前置判。

模型一律用假链替掉（`turn_stream.build_chain` 被 monkeypatch），只有一条真链空 key 的用例
走真降级——它打的还是 127.0.0.1:9，没有任何外呼。
`render_agent_text()` 是前端 DebateStream 将要照做的最小口径，落在这里是为了把契约钉成可跑的断言：
正文按 attempt 分桶累加，`validation.failed` 之前那几桶整桶作废，终稿取最后一个非空桶。
"""

import json
from collections import defaultdict

import pytest
from fastapi.testclient import TestClient
from test_debate_turn import FakeChain

from app.api import turn_stream
from app.config import Settings
from app.llm import factory
from app.llm.fallback import TEMPLATE_REPLY
from app.main import app

TOPIC = "远程办公应当成为默认选项"
CONTENT = "数据显示远程办公效率更高，所以所有人都该回家办公。"
LOGIC_DRAFT = "[LOGIC] 你的推论跳了一步：样本量撑不起「所有人都该」"


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def open_session(client, **overrides) -> str:
    body = {"topic": TOPIC, "stance": "pro"}
    body.update(overrides)
    resp = client.post("/api/sessions", json=body)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["session_id"]


def post_turn(client, sid: str, key: str, content: str = CONTENT):
    return client.post(
        f"/api/sessions/{sid}/turns",
        json={"content": content},
        headers={"Idempotency-Key": key},
    )


def frames_of(resp) -> list[tuple[str, dict]]:
    frames = []
    for block in resp.text.strip().split("\n\n"):
        event = None
        data = None
        for line in block.splitlines():
            if line.startswith("event: "):
                event = line[len("event: ") :]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: ") :])
        frames.append((event, data))
    return frames


def names_of(frames: list[tuple[str, dict]]) -> list[str]:
    return [event for event, _ in frames]


def render_agent_text(frames: list[tuple[str, dict]]) -> str:
    """按帧序还原本回合该显示的那一句：failed 之前累积的正文整桶作废。"""
    buckets: dict[int, list[str]] = defaultdict(list)
    for event, data in frames:
        if event == "message.delta":
            buckets[int(data["attempt"])].append(data["text"])
        elif event == "validation.failed":
            for attempt in [a for a in buckets if a < int(data["attempt"])]:
                buckets.pop(attempt)
    return "".join(buckets[max(buckets)]) if buckets else ""


def use_chain(monkeypatch, chain) -> None:
    monkeypatch.setattr(turn_stream, "build_chain", lambda: chain)


def test_first_pass_turn_streams_started_delta_layer_done(client, monkeypatch):
    use_chain(monkeypatch, FakeChain(drafts=[LOGIC_DRAFT]))
    frames = frames_of(post_turn(client, open_session(client), "k1"))

    assert names_of(frames) == [
        "turn.started",
        "message.delta",
        "message.layer",
        "turn.done",
    ]
    assert [data["seq"] for _, data in frames] == [1, 2, 3, 4], "每帧都带回合内单调 seq"
    started = frames[0][1]
    assert set(started) == {"seq", "trace_id", "turn_index", "ts", "cfg"}
    assert started["turn_index"] == 1
    assert started["cfg"] == {
        "difficulty": "competitive",
        "strictness": "strict",
        "mode": "workflow",
    }
    assert frames[-1][1]["usage"] == {"prompt": 0, "completion": 0}
    assert render_agent_text(frames) == LOGIC_DRAFT


def test_retry_frames_end_on_the_template_not_on_a_discarded_draft(client, monkeypatch):
    use_chain(monkeypatch, FakeChain(drafts=["没有层标签的一稿", "还是没有层标签"]))
    frames = frames_of(post_turn(client, open_session(client), "k1"))

    assert names_of(frames) == [
        "turn.started",
        "message.delta",
        "validation.failed",
        "message.delta",
        "validation.failed",
        "message.delta",
        "turn.done",
    ]
    # 三稿：attempt 0 被判作废、1 也作废、2 是兜底模板——终稿不能是半句废稿
    assert [d["attempt"] for e, d in frames if e == "message.delta"] == [0, 1, 2]
    assert [d["attempt"] for e, d in frames if e == "validation.failed"] == [1, 2]
    assert render_agent_text(frames) == TEMPLATE_REPLY
    assert "message.layer" not in names_of(frames), "模板不是模型输出，不打层标签"


def test_fallback_event_precedes_the_body_it_explains(client, monkeypatch):
    use_chain(monkeypatch, FakeChain(drafts=[LOGIC_DRAFT], tiers=[2]))
    names = names_of(frames_of(post_turn(client, open_session(client), "k1")))

    assert names.count("llm.fallback") == 1
    assert names.index("llm.fallback") < names.index("message.delta"), "角标不能晚于正文"


def test_real_chain_without_any_key_still_streams_a_finished_turn(client, monkeypatch):
    """不 mock 链：空 key + 打不通的本地地址，看真降级链能不能把这个回合推完。"""
    monkeypatch.setattr(
        factory,
        "get_settings",
        lambda: Settings(deepseek_api_key="", ollama_host="http://127.0.0.1:9"),
    )
    sid = open_session(client)
    resp = post_turn(client, sid, "k-real")
    frames = frames_of(resp)

    assert resp.headers["content-type"].startswith("text/event-stream")
    names = names_of(frames)
    assert names[0] == "turn.started"
    assert names[-1] == "turn.done"
    assert names.count("llm.fallback") == 1
    assert render_agent_text(frames) == TEMPLATE_REPLY
    assert client.get(f"/api/sessions/{sid}").json()["data"]["turn_count"] == 1


def test_unknown_session_is_reported_with_a_code(client):
    resp = post_turn(client, "nope", "k1")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "SESSION_NOT_FOUND"


def test_cookie_bound_to_another_device_is_refused(client):
    sid = open_session(client)
    resp = client.post(
        f"/api/sessions/{sid}/turns",
        json={"content": CONTENT},
        headers={"Idempotency-Key": "k1"},
        cookies={"arena_device": "another-device"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "IDENTITY_MISMATCH"


def test_replayed_idempotency_key_runs_the_turn_only_once(client, monkeypatch):
    use_chain(monkeypatch, FakeChain(drafts=[LOGIC_DRAFT, LOGIC_DRAFT]))
    sid = open_session(client)

    assert post_turn(client, sid, "same-key").status_code == 200
    replay = post_turn(client, sid, "same-key")
    assert replay.status_code == 409
    assert replay.json()["error"]["code"] == "IDEMPOTENCY_REPLAY"
    assert client.get(f"/api/sessions/{sid}").json()["data"]["turn_count"] == 1

    assert post_turn(client, sid, "fresh-key").status_code == 200
    data = client.get(f"/api/sessions/{sid}").json()["data"]
    assert data["turn_count"] == 2
    assert "user_id" not in data, "服务端身份不回显"


def test_turns_reject_identity_and_immutable_keys(client, monkeypatch):
    """body 里带 user_id / persona 曾被一路穿透到 501，现在 extra='forbid' 当场 422。"""
    use_chain(monkeypatch, FakeChain(drafts=[LOGIC_DRAFT]))
    sid = open_session(client)
    url = f"/api/sessions/{sid}/turns"
    with_key = {"headers": {"Idempotency-Key": "k1"}}

    rejected = [
        client.post(url, json={"content": CONTENT, "user_id": "someone"}, **with_key),
        client.post(url, json={"content": CONTENT, "persona": "coach"}, **with_key),
        client.post(url, json={"content": CONTENT}, params={"user_id": "someone"}, **with_key),
        client.post(url, json={"content": CONTENT}),  # 没带 Idempotency-Key
    ]
    assert [resp.status_code for resp in rejected] == [422, 422, 422, 422]
    assert post_turn(client, sid, "k2").status_code == 200, "同一个会话照常能发回合"


def test_agent_loop_session_is_refused_instead_of_running_the_other_graph(client):
    resp = client.post(
        "/api/sessions", json={"topic": TOPIC, "stance": "pro", "mode": "agent-loop"}
    )
    assert resp.status_code == 501
    assert "agent-loop" in resp.json()["detail"]
