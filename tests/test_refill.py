"""Queued tests can use each free slot after a completed batch."""

import pytest


@pytest.mark.parametrize("outcome", ["pass", "fail", "cancel"])
def test_refills_free_slots_after_batch(pytester, outcome):
    pytester.makeini("""
        [pytest]
        max_asyncio_tasks = 3
        asyncio_task_timeout = 2
    """)
    pytester.makepyfile(
        """
        import asyncio
        import pytest

        finished = set()
        active = set()
        ready = asyncio.Event()

        @pytest.mark.parametrize("case", range(6))
        @pytest.mark.asyncio_cooperative
        async def test_batch(case):
            if case < 3:
                try:
                    FIRST_OUTCOME
                finally:
                    await asyncio.sleep(0)
                    finished.add(case)
                return

            assert finished == {0, 1, 2}
            active.add(case)
            try:
                assert len(active) <= 3
                if active == {3, 4, 5}:
                    ready.set()
                # This guard exposes a free slot that the scheduler leaves idle.
                # It is not a throughput or elapsed-time performance assertion.
                await asyncio.wait_for(ready.wait(), timeout=1)
            finally:
                active.remove(case)
        """.replace(
            "FIRST_OUTCOME",
            {
                "pass": "pass",
                "fail": "raise ValueError('first batch failure')",
                "cancel": "await asyncio.Event().wait()",
            }[outcome],
        )
    )
    result = pytester.runpytest()
    result.assert_outcomes(
        passed=6 if outcome == "pass" else 3,
        failed=0 if outcome == "pass" else 3,
    )
    if outcome == "fail":
        result.stdout.fnmatch_lines(["*ValueError: first batch failure*"])
    elif outcome == "cancel":
        result.stdout.fnmatch_lines(["*CancelledError: Test took too long*"])
