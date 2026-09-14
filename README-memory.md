# Completed test state

The cooperative scheduler owns a task until it completes, runs fixture teardown,
and finishes the pytest reporting protocol. It must then release that task and
the function-scoped fixture cache. Failure reports retain the rendered error;
they must not retain live fixture values through a completed task's traceback.

The repair removes the completed-task list, removes finished coroutines from the
item map, and removes completed tasks from the cancellation set. The synchronous
reporting wrapper releases its result after pytest consumes it. The scheduler
clears function-scoped fixture state after reporting and before any retry.

The default concurrency remains 100. Tests cover successful, failed, and
cancelled tasks, fixture teardown, and release before the next test starts. The
existing retry and fixture tests remain part of validation.

Validation used Linux ARM64, Python 3.12.14, pytest 7.4.4, and identical frozen
unit-test dependencies. The unchanged revision had 75 passes, 16 skips, and two
failures. This revision has 80 passes, 16 skips, and the same two failures:
`example/hypothesis_test.py::test_a` rejects its function-scoped Hypothesis fixture;
`tests/test_fixture.py::test_tmp_path` receives a pytest stash KeyError in its child
run. The five new ownership tests pass. The full suite remains non-green.

At concurrency 100, the unchanged plugin retained all 4,000 completed 128 KiB
fixtures and reached 717,832,192 bytes of peak process RSS. Three repaired runs
retained zero fixtures, with peak RSS of 188,116,992, 186,630,144, and 186,511,360
bytes. These measurements used the application's pytest 6.2.5 dependency image.
The workload checks release before process shutdown and performs no cache clearing.

## Refill after a completed batch

When a batch completed, the scheduler added only one queued test before it
waited again. Free slots remained unused until another completion or scheduler
wake-up. The scheduler now fills every available slot in FIFO order. It still
waits for cancellation cleanup and reporting, and it never exceeds the selected
limit. The default remains 100.

Three regressions check a completed, failed, and cancelled first batch. Every
case requires the next batch to reach a shared barrier while slots are free.
The original code fails all three; the repaired code passes them. All ten
focused ownership, wait, and refill checks pass on Python 3.11, 3.12, and 3.13.

The matched Python 3.12 full baseline has 82 passes, two failures, and 16 skips.
The repaired full suite has 85 passes, the same two failures, and 16 skips on
each of Python 3.11–3.13. The failures remain the Hypothesis function-fixture
health check and the tmp-path child-test stash failure. Exact reports preserve
their errors. Unit dependencies match the prior locked pytest 7.4.4 environment;
before and after use identical versions. All runs use bounded Linux ARM64
containers. The three repaired versions use one source archive.

This scheduling repair makes the configured slots available. It is not a
production pricing memory reduction, and it does not change the earlier
ownership-only memory measurements above.
