"""ASTRA Core deterministic command system."""

from dataclasses import dataclass, field
from typing import Dict, List, Callable, Any, Optional, Tuple
from enum import Enum
import threading
from collections import defaultdict

from astra.core.ids import CommandId
from astra.core.logging import get_logger
from astra.core.exceptions import CommandError


class CommandStatus(Enum):
    """Status of a command in the execution pipeline."""

    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Command:
    """A deterministic simulation command."""

    id: CommandId
    name: str
    tick: int
    sequence: int
    data: Dict[str, Any] = field(default_factory=dict)
    status: CommandStatus = CommandStatus.PENDING
    result: Any = None
    error: Optional[str] = None

    @classmethod
    def create(
        cls,
        name: str,
        tick: int,
        sequence: int,
        data: Optional[Dict[str, Any]] = None,
    ) -> "Command":
        """Create a new command with a generated ID."""
        cmd_id = CommandId.generate(tick, sequence)
        return cls(
            id=cmd_id,
            name=name,
            tick=tick,
            sequence=sequence,
            data=data or {},
        )

    def __lt__(self, other: "Command") -> bool:
        """Compare commands for sorting (deterministic ordering)."""
        if self.tick != other.tick:
            return self.tick < other.tick
        return self.sequence < other.sequence


# Handler type
CommandHandler = Callable[[Command], Any]


@dataclass
class CommandRegistration:
    """Registration info for a command handler."""

    name: str
    handler: CommandHandler
    priority: int = 0


class CommandHistory:
    """Stores command execution history for replay."""

    def __init__(self):
        self._commands: List[Command] = []
        self._by_tick: Dict[int, List[Command]] = defaultdict(list)
        self._lock = threading.Lock()

    def record(self, command: Command):
        """Record a command in history."""
        with self._lock:
            self._commands.append(command)
            self._by_tick[command.tick].append(command)

    def get_commands(self, tick: Optional[int] = None) -> List[Command]:
        """Get commands, optionally filtered by tick."""
        with self._lock:
            if tick is not None:
                return sorted(self._by_tick.get(tick, []))
            return sorted(self._commands)

    def get_history(self) -> List[Command]:
        """Get full command history."""
        with self._lock:
            return sorted(self._commands)

    def clear(self):
        """Clear command history."""
        with self._lock:
            self._commands.clear()
            self._by_tick.clear()

    def get_replay_sequence(self, from_tick: int = 0, to_tick: Optional[int] = None) -> List[Command]:
        """Get commands in replay order for a tick range."""
        with self._lock:
            commands = self._commands.copy()

        # Filter by tick range
        if from_tick > 0:
            commands = [c for c in commands if c.tick >= from_tick]
        if to_tick is not None:
            commands = [c for c in commands if c.tick <= to_tick]

        # Sort deterministically
        return sorted(commands)


class CommandDispatcher:
    """Dispatches and executes commands deterministically."""

    def __init__(self):
        self._handlers: Dict[str, CommandRegistration] = {}
        self._history = CommandHistory()
        self._pending: List[Command] = []
        self._sequence_counter = 0
        self._lock = threading.Lock()
        self._logger = get_logger("command_dispatcher")

    def register(self, name: str, handler: CommandHandler, priority: int = 0):
        """Register a command handler."""
        with self._lock:
            self._handlers[name] = CommandRegistration(name=name, handler=handler, priority=priority)
            self._logger.debug(f"Registered command handler: {name}")

    def unregister(self, name: str):
        """Unregister a command handler."""
        with self._lock:
            if name in self._handlers:
                del self._handlers[name]
                self._logger.debug(f"Unregistered command handler: {name}")

    def submit(
        self,
        name: str,
        tick: int,
        data: Optional[Dict[str, Any]] = None,
    ) -> Command:
        """Submit a command for execution."""
        with self._lock:
            self._sequence_counter += 1
            command = Command.create(
                name=name,
                tick=tick,
                sequence=self._sequence_counter,
                data=data,
            )
            self._pending.append(command)
            self._logger.debug(f"Submitted command: {name} at tick {tick}")
            return command

    def execute_pending(self, current_tick: int) -> List[Tuple[Command, Any, Optional[str]]]:
        """Execute all pending commands for the given tick.
        
        Returns list of (command, result, error) tuples.
        """
        results = []

        with self._lock:
            # Get commands for this tick
            commands_to_execute = [c for c in self._pending if c.tick == current_tick]
            # Remove from pending
            self._pending = [c for c in self._pending if c.tick != current_tick]

        # Sort for deterministic ordering
        commands_to_execute.sort()

        for command in commands_to_execute:
            result = None
            error = None

            registration = self._handlers.get(command.name)
            if registration is None:
                error = f"No handler registered for command: {command.name}"
                command.status = CommandStatus.FAILED
                command.error = error
                self._logger.error(error)
            else:
                try:
                    command.status = CommandStatus.EXECUTING
                    result = registration.handler(command)
                    command.status = CommandStatus.COMPLETED
                    command.result = result
                    self._logger.debug(f"Executed command: {command.name}")
                except Exception as e:
                    error = str(e)
                    command.status = CommandStatus.FAILED
                    command.error = error
                    self._logger.error(f"Command failed: {command.name}: {e}")

            # Record in history
            self._history.record(command)
            results.append((command, result, error))

        return results

    def replay_command(self, command: Command) -> Any:
        """Replay a single command from history."""
        registration = self._handlers.get(command.name)
        if registration is None:
            raise CommandError(
                f"No handler for replay: {command.name}",
                command_id=command.id.value,
                tick=command.tick,
            )

        command.status = CommandStatus.EXECUTING
        try:
            result = registration.handler(command)
            command.status = CommandStatus.COMPLETED
            command.result = result
            return result
        except Exception as e:
            command.status = CommandStatus.FAILED
            command.error = str(e)
            raise

    def get_history(self) -> CommandHistory:
        """Get the command history."""
        return self._history

    def get_pending_count(self) -> int:
        """Get count of pending commands."""
        with self._lock:
            return len(self._pending)

    def clear_pending(self):
        """Clear all pending commands."""
        with self._lock:
            self._pending.clear()
            self._sequence_counter = 0
