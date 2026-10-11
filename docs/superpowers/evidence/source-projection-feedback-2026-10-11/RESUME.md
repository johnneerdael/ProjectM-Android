# Resumption check after a transport interruption

The current native screenshot/10-second clip and committed source qualification
are complete. Continue the pending source-math increment on the **same Zylot Spiral**.
Read `resume-checkpoint.json` for branch, identities, artifacts and exact next steps.

At every resumed turn:

1. Call get_goal and report an unexpected paused/blocked state. Do not manufacture
   a replacement goal or mark completion. This tool interface cannot set active;
   the user/client goal control must resume it.
2. Check current git HEAD/status in the recorded worktree and read the current
   source/artifact state. Preserve unrelated work and original prediction files.
3. Check known tool session handles and live agents. A saved PID, log, intent,
   lock or this checkpoint alone is not liveness evidence. Poll a confirmed live
   handle; do not restart on a transient observation timeout.
4. If a handle is terminal, inspect its exit code and final evidence before
   retrying. Restart only an unfinished task whose failure has been diagnosed or
   whose relevant external state has changed; never re-run the same failure blindly.
5. Resume the first unmet verification/integration step, preserve qualifications,
   and commit/push verified increments. Update this checkpoint at handoff boundaries.

This is a work recovery checklist, **not automatic ChatGPT reconnection**. The
assistant cannot observe a disconnected server stream while it is not running,
click Retry from inside a failed response, or schedule its own next turn through
the tools currently exposed. Hosted Page/site schedules do not resume this coding
thread. Use `/goal resume` when the goal control is blocked. The client/service
would need a supported transport-retry facility for fully automatic retry.

Reported platform error:
`stream disconnected before completion: An error occurred while processing your request`
Request ID: `4a2e1d49-9bdd-42dc-a41d-f2722ce8d622`.
Observed goal status was blocked; its cause is not established by these tools.
No engineering work should be credited to a retry until current evidence verifies it.

## Supported client retry configuration

Local Codex CLI is0.162.1. A filtered read of the user's configuration found no
model-provider retry overrides. OpenAI's [configuration reference](https://developers.openai.com/codex/config-reference/)
documents `model_providers.<id>.stream_max_retries` for SSE interruptions (default5)
and `request_max_retries` for HTTP requests (default4). Provider settings must be
in user configuration; project-scoped provider entries are ignored. Raising
retries may help the SSE transport, but the current transport and cause are not
established here, and it does not reactivate a blocked goal. This session cannot
write `~/.codex/config.toml`; no retry or provider configuration was changed.
