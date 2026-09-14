"""Completed tests must release results and function fixtures during the run."""

import pytest


@pytest.mark.parametrize("outcome", ["pass", "fail", "cancel"])
def test_completed_test_releases_objects_before_next_test(testdir, outcome):
    testdir.makeini("""
        [pytest]
        max_asyncio_tasks = 1
        asyncio_task_timeout = 1
    """)
    testdir.makepyfile(
        """
        import asyncio
        import gc
        import weakref
        import pytest

        refs = []
        finalized = []

        class Payload:
            pass

        @pytest.fixture
        async def payload():
            value = Payload()
            refs.append(weakref.ref(value))
            yield value
            finalized.append(True)

        @pytest.mark.asyncio_cooperative
        async def test_first(payload):
            local = Payload()
            refs.append(weakref.ref(local))
            OUTCOME

        @pytest.mark.asyncio_cooperative
        async def test_next():
            gc.collect()
            assert finalized == [True]
            assert len(refs) == 2
            assert [ref() for ref in refs] == [None, None]
    """.replace(
            "OUTCOME",
            {
                "pass": "assert payload is not local",
                "fail": "raise ValueError('original failure remains visible')",
                "cancel": "await asyncio.Event().wait()",
            }[outcome],
        )
    )
    result = testdir.runpytest()
    result.assert_outcomes(
        passed=2 if outcome == "pass" else 1, failed=0 if outcome == "pass" else 1
    )
    if outcome == "fail":
        result.stdout.fnmatch_lines(["*ValueError: original failure remains visible*"])


def test_retry_gets_fresh_function_fixture(testdir):
    testdir.makepyfile("""
        import pytest

        starts = []
        stops = []

        @pytest.fixture
        def payload():
            value = object()
            starts.append(value)
            yield value
            stops.append(value)

        @pytest.mark.flaky
        @pytest.mark.asyncio_cooperative
        async def test_retry(payload):
            assert len(starts) == 2
            assert payload is starts[1]
            assert starts[0] is not starts[1]
            assert stops == [starts[0]]

        def test_teardown():
            assert stops == starts
    """)
    result = testdir.runpytest()
    result.assert_outcomes(passed=2)


def test_reporting_preserves_caller_owned_exec_namespace(testdir):
    testdir.makeini("""
        [pytest]
        max_asyncio_tasks = 1
    """)
    testdir.makepyfile("""
        import pytest

        sentinel = object()
        namespace = {"value": sentinel}

        @pytest.mark.asyncio_cooperative
        async def test_first():
            exec("raise ValueError('exec failure')", namespace)

        @pytest.mark.asyncio_cooperative
        async def test_next():
            assert namespace["value"] is sentinel
    """)
    result = testdir.runpytest()
    result.assert_outcomes(passed=1, failed=1)
