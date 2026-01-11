## Global Safety Guardrails

### Token/Cost Limits
```
- Max iterations per stage: defined above
- Max total tokens per session: 500,000
- Alert user if approaching 80% of token budget
```

### Error Handling
```
- If MCP LinkedIn fetch fails 3x: surface error, suggest manual input
- If any stage fails max iterations: 
    - Save state
    - Surface blocker summary to user
    - Allow manual override or retry with modified params
```

### Data Privacy
```
- No PII sent to external APIs beyond LinkedIn MCP and job listing fetch
- All artifacts stored client-side only
- User can export/delete all data at any time
```

---

