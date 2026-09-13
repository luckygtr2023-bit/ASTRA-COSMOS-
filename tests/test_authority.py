"""Test suite for ASTRA Core authority and threading."""

import pytest
import threading
import time
from astra.core.threading import AuthorityContext, SimulationThread, AuthorityToken
from astra.core.exceptions import AuthorityError


class TestAuthorityContext:
    """Tests for AuthorityContext."""

    def test_authority_granted_in_context(self):
        """Test that authority is granted within context."""
        with AuthorityContext("test_operation") as token:
            assert token is not None
            assert isinstance(token, AuthorityToken)
            assert token.thread_id == threading.current_thread().ident

    def test_authority_released_after_context(self):
        """Test that authority is released after context exits."""
        with AuthorityContext("test_operation") as token:
            current_token = AuthorityContext.get_current_token()
            assert current_token is not None

        # After context, token should be cleared
        assert AuthorityContext.get_current_token() is None

    def test_require_authority_success(self):
        """Test that require_authority succeeds with valid authority."""
        with AuthorityContext("test_operation", granted_operations={"read", "write"}):
            # Should not raise
            AuthorityContext.require_authority("read")
            AuthorityContext.require_authority("write")

    def test_require_authority_failure(self):
        """Test that require_authority fails without authority."""
        # Outside context - should fail
        with pytest.raises(AuthorityError):
            AuthorityContext.require_authority("write")

    def test_has_authority(self):
        """Test has_authority checks."""
        assert not AuthorityContext.has_authority("anything")

        with AuthorityContext("test", granted_operations={"read"}):
            assert AuthorityContext.has_authority("read")
            assert not AuthorityContext.has_authority("write")

    def test_nested_contexts(self):
        """Test nested authority contexts."""
        with AuthorityContext("outer"):
            outer_token = AuthorityContext.get_current_token()
            assert outer_token is not None

            with AuthorityContext("inner"):
                inner_token = AuthorityContext.get_current_token()
                assert inner_token is not None

            # Back to outer
            assert AuthorityContext.get_current_token() is None  # Context clears on exit


class TestSimulationThread:
    """Tests for SimulationThread."""

    def test_simulation_thread_creation(self):
        """Test simulation thread creation."""
        sim_thread = SimulationThread("TestThread")
        assert not sim_thread.is_running()
        assert not sim_thread.is_simulation_thread()

    def test_simulation_thread_start_stop(self):
        """Test starting and stopping simulation thread."""
        sim_thread = SimulationThread("TestThread")
        executed = []

        def target():
            executed.append(True)
            # Run briefly then exit
            time.sleep(0.1)

        sim_thread.start(target)
        time.sleep(0.05)
        assert sim_thread.is_running()

        sim_thread.stop()
        assert not sim_thread.is_running()
        assert len(executed) > 0

    def test_is_simulation_thread(self):
        """Test is_simulation_thread check."""
        sim_thread = SimulationThread("TestThread")
        called_on_sim_thread = []

        def target():
            called_on_sim_thread.append(sim_thread.is_simulation_thread())
            time.sleep(0.05)

        sim_thread.start(target)
        time.sleep(0.1)
        sim_thread.stop()

        assert len(called_on_sim_thread) > 0
        assert all(called_on_sim_thread)

    def test_require_simulation_thread(self):
        """Test require_simulation_thread."""
        sim_thread = SimulationThread("TestThread")
        errors = []

        def target():
            try:
                sim_thread.require_simulation_thread("test_op")
            except AuthorityError as e:
                errors.append(e)
            time.sleep(0.05)

        sim_thread.start(target)
        time.sleep(0.1)
        sim_thread.stop()

        # Should have no errors when called from simulation thread
        assert len(errors) == 0

    def test_require_simulation_thread_fails_off_thread(self):
        """Test that require_simulation_thread fails off simulation thread."""
        sim_thread = SimulationThread("TestThread")

        # Call from main thread (not simulation thread)
        with pytest.raises(AuthorityError):
            sim_thread.require_simulation_thread("test_op")


class TestAuthorityEnforcement:
    """Tests for actual authority enforcement."""

    def test_authority_token_properties(self):
        """Test AuthorityToken properties."""
        token = AuthorityToken(
            thread_id=123,
            context_id="ctx_1",
            granted_operations={"read", "write"},
        )
        assert token.thread_id == 123
        assert token.context_id == "ctx_1"
        assert token.can_perform("read")
        assert token.can_perform("write")
        assert not token.can_perform("delete")

    def test_empty_granted_operations_means_all(self):
        """Test that empty granted_operations allows all."""
        token = AuthorityToken(
            thread_id=123,
            context_id="ctx_1",
            granted_operations=set(),
        )
        # Empty set means all operations allowed
        assert token.can_perform("anything")

    def test_thread_safety_of_authority(self):
        """Test that authority is thread-local."""
        results = {"thread1": None, "thread2": None}

        def thread1_func():
            with AuthorityContext("op1") as token:
                results["thread1"] = token.context_id
                time.sleep(0.1)

        def thread2_func():
            time.sleep(0.05)  # Start slightly later
            with AuthorityContext("op2") as token:
                results["thread2"] = token.context_id

        t1 = threading.Thread(target=thread1_func)
        t2 = threading.Thread(target=thread2_func)

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Both threads should have gotten their own tokens
        assert results["thread1"] is not None
        assert results["thread2"] is not None
        assert results["thread1"] != results["thread2"]
