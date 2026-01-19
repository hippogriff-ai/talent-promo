---
active: true
iteration: 232
max_iterations: 0
completion_promise: null
started_at: "2026-01-15T13:42:50Z"
---

read specs/memory_feature.md to understand the
requirement, check memory_implementation_plan.md file to pick the most important work to work on. Think hard, you
 may use up to 50 subagents to achieve your goals, including writing simple and DRY code
and adding ample tests and ensure the behavior and bug free. You should use only one
subagent to run the tests. In each loop, first think hard to pick the most important thing
to work on from memory_implementation_plan.md file, do not assume a feature is not implemented, explore the code
base to see what is the status. Read continuity file to see what has been done in the
entire project, which may contain things ourside of the memory_implementation_plan.md. Then start implementing
choosing the simplest solution, do not complicate things. Afterwards, add tests and add
docstr for the test so that we can see what tests can be simplified in future iterations.
Then review the code change, fix bugs, security issues, or tidy up the code by better
abstraction. You also need to clean up dead code. After you finish the one task you picked
up, document in memory_implementation_plan.md with done and todo items with details includind which files were
changed, and continuity file on high level what you did. Then next loop. The final product
should be end to end functional, with robust unit tests and e2e tests, and eval using
langsmith sdk. You need to ensure there is a feedback loop exists at local development
time, so that we can tune the prompt with the harness instead of tweaking the prompt
standalone. --max-iterations 30 --completion-promise “I-REMEMBER”
