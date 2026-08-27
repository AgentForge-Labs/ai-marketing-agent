# Semantic Browser Service — `visser23/semantic-browser`

Token-efficient agentic browsing: live Chromium → ~540 token oda metni (standart 10k yerine, %96 tasarruf, 100% success vs %24).

## Kaynak
- https://github.com/visser23/semantic-browser (22★, v1.3.2, MIT)
- `pip install "semantic-browser[managed]"` + `semantic-browser install-browser`
- Docs: `docs/planner_contract.md`, `docs/api_reference.md`, `docs/runtime_modes.md`

## Kurulum

```bash
pip install "semantic-browser[managed]"
semantic-browser install-browser
# service
pip install "semantic-browser[server]"
semantic-browser serve --host 127.0.0.1 --port 8765 --api-token vault://semantic/browser/token
```

## Mimari Entegrasyon (docs/03)

`schemas/site-adapter.schema.json:semanticBrowser`:

```json
"semanticBrowser": {
  "enabled": true,
  "serviceUrl": "http://127.0.0.1:8765",
  "mode": "summary",
  "topActions": 25,
  "useForDiscovery": true,
  "useForDriftRepair": true
}
```

Runner `biometricMouse` ile birlikte kullanır: `humanMouse` hareketi + `semantic` planlama.

## Kullanım — Python (ManagedSession)

```python
from semantic_browser import ManagedSession
from semantic_browser.models import ActionRequest

async def run(url, task):
    session = await ManagedSession.launch(headful=False)
    runtime = session.runtime
    await runtime.navigate(url)
    obs = await runtime.observe(mode="summary")
    print(obs.planner.room_text)  # prose, not JSON soup
    # obs.available_actions: top 25, `more` ile progressive
    # obs.planner.blockers: cookie_banner detected -> dismiss [act-...]
    for _ in range(25):
        action_id = call_your_llm(obs.planner.room_text, task)  # tek action_id
        if action_id == "done": break
        result = await runtime.act(ActionRequest(action_id=action_id))
        obs = result.observation  # delta
    await session.close()
```

## CLI / HTTP

```bash
semantic-browser portal --url https://example.com --headless
semantic-browser observe --session <id> --mode summary
semantic-browser act --session <id> --action <action_id>
semantic-browser serve --host 127.0.0.1 --port 8765 --api-token $TOKEN
# GET /health -> {status, version, active_sessions} (unauth)
```

## Neden (benchmarks/manifest.json 25-task)

- Standard browser tooling: 24% (6/25), 10118 input tokens
- OpenClaw: 72% (18/25), 6833 tokens
- **Semantic Browser: 100% (25/25), 540 input / 14 output, $0.004/req** vs $0.041 standard

Mapper: `Live page → extract semantic tree → group regions → curate actions → render room_text → LLM picks ID → runtime executes → observe delta`.

## Notlar
- Cookie/banner/modals auto-detected (`! Cookie consent banner detected -> dismiss`).
- 3 interface: Python API / CLI / HTTP service; CDP attach de destekler.
- Drift repair'de `docs/03` locator önceliği (role/label/placeholder) yanında semantic mapping fallback.
```

