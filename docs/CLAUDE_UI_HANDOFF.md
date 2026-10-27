# Claude UI Handoff

- Base commit: 6bfd776 (rollback tag: `pre-ui-polish-rollback`)
- Committed: see final commit on master (message `feat(ui): ...`). Pushed: NO. Live site verified: NO. Real browser inspection: NOT done (only Streamlit AppTest).

## Files modified
- src/aegis/ui/theme.py: shell CSS (container width, header, sidebar KV/notes, metrics, inputs, alerts, tables, charts, tabs, mobile breakpoint)
- src/aegis/ui/components.py: new compact `render_header`, `render_provenance_sidebar` (fixed broken `<b>...:**` markup, removed hardcoded commit/test-count/version labels)
- src/aegis/ui/app.py: emoji removed from tab labels; `&bull;` -> `·`; solver banner now distinguishes INFEASIBLE (error) from other non-optimal statuses such as TIME_LIMIT (warning)

## Tests executed
- ruff check src/aegis/ui: pass
- pytest tests/test_ui_and_explainability.py: 11 passed
- Streamlit AppTest of app.py: no exceptions, 5 tabs render
- Full pytest: all passed (exit 0)

## Known issues (backend, not fixed)
- Baseline stochastic_milp solve on Overview returns status TIME_LIMIT with a 10 s limit in AppTest; previously misreported as infeasible. Investigate solver time limit / result handling.
- Inner tab labels in Explainability still contain emojis (app.py).
- `use_container_width` deprecation warnings (use `width='stretch'`).

## Remaining UI tasks (priority)
1. Overview: KPI grouping, map/forecast layout, risk table styling.
2. Scenario Lab: group controls in bordered containers, prominent primary Run button, cost/shortage summary cards.
3. Explainability / Stress / Governance: consistent section headers, remove inner emojis.
4. Browser verification of Overview + Scenario Lab at desktop and mobile width.

## Next commands
```
.venv/Scripts/python.exe -m ruff check src
.venv/Scripts/python.exe -m pytest tests -q
.venv/Scripts/python.exe -m streamlit run app.py
git push origin master   # only after browser verification
```
