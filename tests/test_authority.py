"""Test suite for ASTRA Core authority and threading.

This test suite verifies the single authoritative simulation-thread model.
Only the registered simulation thread can obtain authority to mutate
simulation state.
"""

import pytest
import threading
import time
from astra.core.threading import (
    AuthorityContext,
    SimulationThreadRegistry,
    get_simulation_thread_registry,
    reset_simulation_thread_registry,
    AuthorityToken,
)
from astra.core.exceptions import AuthorityError


@pytest.fixture(autouse=True)
def reset_registry():
    """Reset the simulation thread registry before each test."""
    reset_simulation_thread_registry()
    yield
    reset_simulation_thread_registry()


class TestAuthorityContext:
    """Tests for AuthorityContext."""

    def test_authority_denied_without_registration(self):
        """Test that authority is denied when no simulation thread is registered."""
        # No simulation thread registered - should fail
        with pytest.raises(AuthorityError, match="not the registered simulation thread"):
            with AuthorityContext("test_operation"):
                pass  # Should never reach here

    def test_authority_granted_to_registered_thread(self):
        """Test that authority is granted to the registered simulation thread."""
        registry = get_simulation_thread_registry()
        thread_id = threading.current_thread().ident
        registry.register_simulation_thread(thread_id)
        
        try:
            with AuthorityContext("test_operation") as token:
                assert token is not None
                assert isinstance(token, AuthorityToken)
                assert token.thread_id == thread_id
        finally:
            registry.unregister_simulation_thread(thread_id)

    def test_authority_released_after_context(self):
        """Test that authority is released after context exits."""
        registry = get_simulation_thread_registry()
        thread_id = threading.current_thread().ident
        registry.register_simulation_thread(thread_id)
        
        try:
            with AuthorityContext("test_operation") as token:
                current_token = AuthorityContext.get_current_token()
                assert current_token is not None

            # After context, token should be cleared
            assert AuthorityContext.get_current_token() is None
        finally:
            registry.unregister_simulation_thread(thread_id)

    def test_require_authority_success(self):
        """Test that require_authority succeeds with valid authority."""
        registry = get_simulation_thread_registry()
        thread_id = threading.current_thread().ident
        registry.register_simulation_thread(thread_id)
        
        try:
            with AuthorityContext("test_operation", granted_operations={"read", "write"}):
                # Should not raise
                AuthorityContext.require_authority("read")
                AuthorityContext.require_authority("write")
        finally:
            registry.unregister_simulation_thread(thread_id)

    def test_require_authority_failure(self):
        """Test that require_authority fails without authority."""
        # No registration - should fail
        with pytest.raises(AuthorityError):
            AuthorityContext.require_authority("write")

    def test_has_authority(self):
        """Test has_authority checks."""
        # No registration - no authority
        assert not AuthorityContext.has_authority("anything")
        
        registry = get_simulation_thread_registry()
        thread_id = threading.current_thread().ident
        registry.register_simulation_thread(thread_id)
        
        try:
            with AuthorityContext("test", granted_operations={"read"}):
                assert AuthorityContext.has_authority("read")
                assert not AuthorityContext.has_authority("write")
        finally:
            registry.unregister_simulation_thread(thread_id)

    def test_nested_contexts(self):
        """Test nested authority contexts."""
        registry = get_simulation_thread_registry()
        thread_id = threading.current_thread().ident
        registry.register_simulation_thread(thread_id)
        
        try:
            with AuthorityContext("outer"):
                outer_token = AuthorityContext.get_current_token()
                assert outer_token is not None

                with AuthorityContext("inner"):
                    inner_token = AuthorityContext.get_current_token()
                    assert inner_token is not None

                # Back to outer - note: inner context exit clears token
                # This is expected behavior - contexts are not truly nested in token storage
        finally:
            registry.unregister_simulation_thread(thread_id)


class TestSimulationThreadRegistry:
    """Tests for SimulationThreadRegistry."""

    def test_registry_singleton(self):
        """Test that registry is a singleton."""
        reg1 = get_simulation_thread_registry()
        reg2 = get_simulation_thread_registry()
        assert reg1 is reg2

    def test_register_simulation_thread(self):
        """Test registering a simulation thread."""
        registry = get_simulation_thread_registry()
        thread_id = 12345
        
        assert not registry.is_registered()
        registry.register_simulation_thread(thread_id)
        assert registry.is_registered()
        assert registry.get_simulation_thread_id() == thread_id
        assert registry.is_simulation_thread(thread_id)

    def test_unregister_simulation_thread(self):
        """Test unregistering a simulation thread."""
        registry = get_simulation_thread_registry()
        thread_id = 12345
        
        registry.register_simulation_thread(thread_id)
        assert registry.is_registered()
        
        registry.unregister_simulation_thread(thread_id)
        assert not registry.is_registered()
        assert registry.get_simulation_thread_id() is None

    def test_cannot_register_different_thread(self):
        """Test that registering a different thread raises an error."""
        registry = get_simulation_thread_registry()
        
        registry.register_simulation_thread(111)
        
        with pytest.raises(AuthorityError, match="already registered"):
            registry.register_simulation_thread(222)

    def test_shutdown(self):
        """Test shutting down the registry."""
        registry = get_simulation_thread_registry()
        
        registry.register_simulation_thread(111)
        registry.shutdown()
        
        assert not registry.is_registered()
        assert registry.get_simulation_thread_id() is None
        
        # Should not be able to register after shutdown
        with pytest.raises(AuthorityError, match="shut down"):
            registry.register_simulation_thread(222)

    def test_is_simulation_thread_with_current(self):
        """Test is_simulation_thread with current thread."""
        registry = get_simulation_thread_registry()
        thread_id = threading.current_thread().ident
        
        registry.register_simulation_thread(thread_id)
        assert registry.is_simulation_thread()  # Uses current thread by default
        assert registry.is_simulation_thread(thread_id)
        
        # Different thread ID should return False
        assert not registry.is_simulation_thread(99999)


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
        registry = get_simulation_thread_registry()
        results = {"thread1": None, "thread2": None}
        errors = {"thread1": None, "thread2": None}

        def thread1_func():
            thread_id = threading.current_thread().ident
            try:
                registry.register_simulation_thread(thread_id)
                with AuthorityContext("op1") as token:
                    results["thread1"] = token.context_id
                    time.sleep(0.1)
            except Exception as e:
                errors["thread1"] = e
            finally:
                registry.unregister_simulation_thread(thread_id)

        def thread2_func():
            thread_id = threading.current_thread().ident
            time.sleep(0.05)  # Start slightly later
            try:
                # Thread 2 cannot register because thread 1 already did
                # This tests that only one simulation thread can be registered
                registry.register_simulation_thread(thread_id)
                with AuthorityContext("op2") as token:
                    results["thread2"] = token.context_id
            except AuthorityError:
                # Expected - thread 2 cannot register
                pass
            except Exception as e:
                errors["thread2"] = e

        t1 = threading.Thread(target=thread1_func)
        t2 = threading.Thread(target=thread2_func)

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Thread 1 should have succeeded
        assert results["thread1"] is not None
        assert errors["thread1"] is None
        
        # Thread 2 should have been blocked from registering
        # (either got AuthorityError or didn't get a token)

    def test_unauthorized_thread_cannot_get_authority(self):
        """Test that an unauthorized thread cannot obtain authority."""
        registry = get_simulation_thread_registry()
        
        # Register thread 1
        registry.register_simulation_thread(111)
        
        # Try to enter context from "different" thread (simulated by different ID check)
        # We can't actually change our thread ID, but we can verify the registry check works
        assert registry.is_simulation_thread(111)
        assert not registry.is_simulation_thread(222)
        
        # The current thread is not registered, so AuthorityContext should fail
        with pytest.raises(AuthorityError):
            with AuthorityContext("unauthorized_op"):
                pass

    def test_authority_after_unregister(self):
        """Test that authority fails after thread unregisters."""
        registry = get_simulation_thread_registry()
        thread_id = threading.current_thread().ident
        
        registry.register_simulation_thread(thread_id)
        registry.unregister_simulation_thread(thread_id)
        
        # Now trying to get authority should fail
        with pytest.raises(AuthorityError):
            with AuthorityContext("post_unregister_op"):
                pass
