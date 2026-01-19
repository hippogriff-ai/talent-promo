---
active: true
iteration: 3
max_iterations: 0
completion_promise: null
started_at: "2026-01-11T18:31:48Z"
---

read the tests needs to pass in @specs/thread_cleanup.md and implement the integration of langgraph with postgres, you need to also setup the local development for langgraph, instead of using local storage, use the local postgres (or supabase if you may). each loop you should first use feature-dev to develop, then code-review, then address the comment, then simplify the code. There should be 5 places of enhancement in each loop, and you should ensure e2e tests passes
