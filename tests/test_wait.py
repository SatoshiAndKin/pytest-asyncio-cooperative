"""The scheduler must sleep until work or its next deadline is ready."""

import json

import pytest


@pytest.mark.parametrize("cancel", [False, True])
def test_waits_for_work_and_awaits_cancelled_cleanup(testdir, cancel):
    testdir.makeini("""
        [pytest]
        max_asyncio_tasks = 4
        asyncio_task_timeout = 1
    """)
    testdir.makeconftest("""
        import asyncio
        import json
        from pathlib import Path
        import time

        original_wait = asyncio.wait
        timeouts = []
        cleanup = []
        started = None

        async def measured_wait(*args, **kwargs):
            timeouts.append(kwargs["timeout"])
            return await original_wait(*args, **kwargs)

        def pytest_sessionstart(session):
            global started
            started = time.monotonic()
            asyncio.wait = measured_wait

        def pytest_sessionfinish(session, exitstatus):
            asyncio.wait = original_wait
            Path("wait.json").write_text(json.dumps({
                "timeouts": timeouts,
                "cleanup": cleanup,
                "elapsed": time.monotonic() - started,
            }))
    """)
    if cancel:
        testdir.makepyfile("""
            import asyncio
            import pytest
            from conftest import cleanup

            @pytest.mark.asyncio_cooperative
            async def test_deadline():
                try:
                    await asyncio.Event().wait()
                finally:
                    await asyncio.sleep(0.2)
                    cleanup.append("finished")
        """)
    else:
        testdir.makepyfile("""
            import asyncio
            import pytest
            from conftest import cleanup

            @pytest.mark.parametrize("case", range(4))
            @pytest.mark.asyncio_cooperative
            async def test_ready(case):
                await asyncio.sleep(0.2)
                cleanup.append(case)
        """)
    result = testdir.runpytest()
    result.assert_outcomes(passed=0 if cancel else 4, failed=1 if cancel else 0)
    measured = json.loads(testdir.tmpdir.join("wait.json").read())
    assert 1 <= len(measured["timeouts"]) <= 6
    assert all(timeout >= 0 for timeout in measured["timeouts"])
    if cancel:
        assert measured["elapsed"] >= 1.2
        assert measured["cleanup"] == ["finished"]
    else:
        assert measured["elapsed"] >= 0.2
        assert sorted(measured["cleanup"]) == list(range(4))
