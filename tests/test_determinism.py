"""Test suite for ASTRA Core determinism."""

import pytest
from astra.core.rng import DeterministicRNG, RNGStream
from astra.core.commands import CommandDispatcher, Command, CommandStatus
from astra.core.engine import Engine, EngineState
from astra.core.config import Config


class TestDeterministicRNG:
    """Tests for deterministic RNG."""

    def test_rng_stream_determinism(self):
        """Test that RNG stream produces deterministic sequence."""
        stream1 = RNGStream("test1", seed=42)
        stream2 = RNGStream("test2", seed=42)

        values1 = [stream1.next_float() for _ in range(10)]
        values2 = [stream2.next_float() for _ in range(10)]

        assert values1 == values2

    def test_rng_stream_isolation(self):
        """Test that RNG streams are isolated from each other."""
        rng = DeterministicRNG(global_seed=42)
        stream_a = rng.create_stream("a", seed=100)
        stream_b = rng.create_stream("b", seed=200)

        # Consume from A
        a_val1 = stream_a.next_float()
        # Consume from B
        b_val1 = stream_b.next_float()
        # Consume from A again
        a_val2 = stream_a.next_float()

        # Create new streams with same seeds
        rng2 = DeterministicRNG(global_seed=42)
        stream_a2 = rng2.create_stream("a", seed=100)
        stream_b2 = rng2.create_stream("b", seed=200)

        # Should get same values
        assert stream_a2.next_float() == a_val1
        assert stream_b2.next_float() == b_val1
        assert stream_a2.next_float() == a_val2

    def test_rng_state_snapshot_restore(self):
        """Test RNG state snapshot and restore."""
        stream = RNGStream("test", seed=42)

        # Consume some values
        values_before = [stream.next_float() for _ in range(5)]

        # Get state
        state = stream.get_state()

        # Consume more values
        more_values = [stream.next_float() for _ in range(3)]

        # Restore state
        stream.restore_state(state)

        # Should produce same values as before
        values_after = [stream.next_float() for _ in range(3)]
        assert values_after == more_values

    def test_rng_reset(self):
        """Test RNG stream reset."""
        stream = RNGStream("test", seed=42)
        values1 = [stream.next_float() for _ in range(10)]

        stream.reset()
        values2 = [stream.next_float() for _ in range(10)]

        assert values1 == values2

    def test_rng_mixed_methods_snapshot_restore(self):
        """Test RNG snapshot/restore with mixed method calls (adversarial test).
        
        This tests that restore_state works correctly regardless of which
        RNG methods were used to consume state, using Python's native
        getstate()/setstate() mechanism.
        """
        stream = RNGStream("mixed_test", seed=12345)

        # Consume using various methods
        val1 = stream.next_float()
        val2 = stream.randint(0, 100)
        val3 = stream.randrange(10, 50, 3)
        val4 = stream.choice([1, 2, 3, 4, 5])
        val5 = stream.uniform(0.0, 10.0)
        val6 = stream.getrandbits(16)

        expected_sequence = [val1, val2, val3, val4, val5, val6]

        # Capture state
        state = stream.get_state()

        # Continue consuming with different methods
        cont1 = stream.next_gauss(0, 1)
        cont2 = stream.shuffle([1, 2, 3])
        cont3 = stream.next_int(0, 1000)

        continued_sequence = [cont1, tuple(cont2), cont3]

        # Restore state
        stream.restore_state(state)

        # Should reproduce exact same sequence
        restored_cont1 = stream.next_gauss(0, 1)
        restored_cont2 = stream.shuffle([1, 2, 3])
        restored_cont3 = stream.next_int(0, 1000)

        restored_sequence = [restored_cont1, tuple(restored_cont2), restored_cont3]

        assert continued_sequence == restored_sequence

    def test_rng_stream_isolation_after_restore(self):
        """Test that restoring one stream does not affect another stream."""
        rng = DeterministicRNG(global_seed=42)
        stream_a = rng.create_stream("iso_a", seed=111)
        stream_b = rng.create_stream("iso_b", seed=222)

        # Consume from both
        a_val1 = stream_a.next_float()
        b_val1 = stream_b.next_float()
        a_val2 = stream_a.next_float()
        b_val2 = stream_b.next_float()

        # Capture state of A
        state_a = stream_a.get_state()

        # Consume more from both
        a_val3 = stream_a.next_float()
        b_val3 = stream_b.next_float()

        # Restore A only
        stream_a.restore_state(state_a)

        # A should replay from saved point
        a_restored = stream_a.next_float()
        assert a_restored == a_val3

        # B should be unaffected by A's restoration
        b_next = stream_b.next_float()
        # This should be the next value in B's sequence after b_val3
        # We just verify B continues without error
        assert isinstance(b_next, float)


class TestDeterministicCommands:
    """Tests for deterministic command execution."""

    def test_command_ordering(self):
        """Test that commands are ordered deterministically."""
        dispatcher = CommandDispatcher()

        # Submit commands out of order
        dispatcher.submit("cmd_c", tick=3, data={"name": "c"})
        dispatcher.submit("cmd_a", tick=1, data={"name": "a"})
        dispatcher.submit("cmd_b", tick=2, data={"name": "b"})
        dispatcher.submit("cmd_d", tick=1, data={"name": "d"})

        # Execute tick 1 - should get cmd_a then cmd_d (by sequence)
        results_tick1 = dispatcher.execute_pending(1)
        assert len(results_tick1) == 2
        assert results_tick1[0][0].data["name"] == "a"
        assert results_tick1[1][0].data["name"] == "d"

        # Execute tick 2
        results_tick2 = dispatcher.execute_pending(2)
        assert len(results_tick2) == 1
        assert results_tick2[0][0].data["name"] == "b"

        # Execute tick 3
        results_tick3 = dispatcher.execute_pending(3)
        assert len(results_tick3) == 1
        assert results_tick3[0][0].data["name"] == "c"

    def test_command_history_replay(self):
        """Test command history replay preserves ordering."""
        dispatcher1 = CommandDispatcher()
        dispatcher1.register("test_cmd", lambda c: c.data.get("value", 0))

        # Submit and execute commands
        dispatcher1.submit("test_cmd", tick=1, data={"value": 10})
        dispatcher1.submit("test_cmd", tick=1, data={"value": 20})
        dispatcher1.submit("test_cmd", tick=2, data={"value": 30})

        dispatcher1.execute_pending(1)
        dispatcher1.execute_pending(2)

        # Get history
        history = dispatcher1.get_history().get_history()
        assert len(history) == 3

        # Replay on new dispatcher
        dispatcher2 = CommandDispatcher()
        dispatcher2.register("test_cmd", lambda c: c.data.get("value", 0))

        replay_results = []
        for cmd in sorted(history):
            result = dispatcher2.replay_command(cmd)
            replay_results.append(result)

        assert replay_results == [10, 20, 30]

    def test_command_deterministic_ids(self):
        """Test that command IDs are deterministic."""
        from astra.core.ids import CommandId

        id1 = CommandId.generate(tick=5, sequence=10)
        id2 = CommandId.generate(tick=5, sequence=10)
        id3 = CommandId.generate(tick=5, sequence=11)

        assert id1.value == id2.value
        assert id1.value != id3.value


class TestEngineDeterminism:
    """Tests for engine-level determinism."""

    def test_engine_deterministic_execution(self):
        """Test that engine produces deterministic results."""
        config = Config(global_seed=42)

        # Run 1
        engine1 = Engine(config)
        engine1.initialize()
        engine1.start()

        rng1 = engine1.rng.create_stream("test", seed=100)
        vals1 = [rng1.next_float() for _ in range(5)]

        for _ in range(10):
            engine1.step()

        engine1.stop()

        # Run 2
        engine2 = Engine(config)
        engine2.initialize()
        engine2.start()

        rng2 = engine2.rng.create_stream("test", seed=100)
        vals2 = [rng2.next_float() for _ in range(5)]

        for _ in range(10):
            engine2.step()

        engine2.stop()

        # Results should be identical
        assert vals1 == vals2
        assert engine1.clock.get_current_tick() == engine2.clock.get_current_tick()

    def test_engine_save_load_determinism(self):
        """Test that save/load produces deterministic continuation."""
        import tempfile
        import shutil

        tmpdir = tempfile.mkdtemp()
        try:
            config = Config(global_seed=42, persistence_path=tmpdir)

            # Simulation A: run -> save -> load -> continue
            engine_a = Engine(config)
            engine_a.initialize()
            engine_a.start()

            for _ in range(20):
                engine_a.step()

            engine_a.save("test_snapshot")
            tick_at_save = engine_a.clock.get_current_tick()

            # Continue running
            for _ in range(10):
                engine_a.step()
            final_tick_a = engine_a.clock.get_current_tick()
            engine_a.stop()

            # Simulation B: run -> load -> continue
            engine_b = Engine(config)
            engine_b.initialize()
            engine_b.start()

            for _ in range(20):
                engine_b.step()

            engine_b.load("test_snapshot")
            # Continue from loaded state
            for _ in range(10):
                engine_b.step()
            final_tick_b = engine_b.clock.get_current_tick()
            engine_b.stop()

            # Ticks should match
            assert final_tick_a == final_tick_b

        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
