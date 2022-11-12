#!/usr/bin/env python
"""Finite state machine.

Simple FSM implementation.

Usage:
    ```python
    class A:
        def run(self, inputs) -> None:
            pass

    class B:
        def run(self, inputs) -> None:
            pass

    def to_b(inputs) -> bool:
        return True

    def to_a(inputs) -> bool:
        return True

    f = Fsm(states=[A(), B()],
            table={A: [(to_b, B)],
                   B: [(to_a, A)]})
    f.run({"input1": 1, "input2": 2})
    ```
"""

import sys
from abc import abstractmethod
from typing import Dict, Generic, Sequence, Tuple, Type, TypeVar, Union

if sys.version_info >= (3, 8):
    from typing import Protocol, runtime_checkable
else:
    from typing_extensions import Protocol, runtime_checkable

if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias

T_FsmInputs = TypeVar("T_FsmInputs", contravariant=True)


@runtime_checkable
class FsmStateRun(Protocol[T_FsmInputs]):
    @abstractmethod
    def run(self, inputs: T_FsmInputs) -> None:
        ...  # pragma: no cover


@runtime_checkable
class FsmStateEnter(Protocol[T_FsmInputs]):
    @abstractmethod
    def on_enter(self, inputs: T_FsmInputs) -> None:
        ...  # pragma: no cover


@runtime_checkable
class FsmStateExit(Protocol[T_FsmInputs]):
    @abstractmethod
    def on_exit(self, inputs: T_FsmInputs) -> None:
        ...  # pragma: no cover


FsmState: TypeAlias = Union[
    FsmStateRun[T_FsmInputs], FsmStateEnter[T_FsmInputs], FsmStateExit[T_FsmInputs]
]


class FsmCondition(Protocol[T_FsmInputs]):
    def __call__(self, inputs: T_FsmInputs) -> bool:
        ...  # pragma: no cover


FsmTable: TypeAlias = Dict[
    Type[FsmState[T_FsmInputs]],
    Sequence[Tuple[FsmCondition[T_FsmInputs], Type[FsmState[T_FsmInputs]]]],
]


class Fsm(Generic[T_FsmInputs]):
    _state_dict: Dict[Type[FsmState], FsmState]
    _table: FsmTable[T_FsmInputs]
    _state: FsmState[T_FsmInputs]

    def __init__(
        self, states: Sequence[FsmState], table: FsmTable[T_FsmInputs]
    ) -> None:
        self._state_dict = {type(s): s for s in states}
        self._table = table
        self._state = self._state_dict[type(states[0])]

    def _transition(
        self, inputs: T_FsmInputs, new_state: Type[FsmState[T_FsmInputs]]
    ) -> None:
        if isinstance(self._state, FsmStateEnter):
            self._state.on_enter(inputs)

        self._state = self._state_dict[new_state]

        if isinstance(self._state, FsmStateExit):
            self._state.on_exit(inputs)

    def _check_transitions(self, inputs: T_FsmInputs) -> None:
        for cond, new_state in self._table[type(self._state)]:
            if cond(inputs):
                self._transition(inputs, new_state)
                return

    def run(self, inputs: T_FsmInputs) -> None:
        self._check_transitions(inputs)
        if isinstance(self._state, FsmStateRun):
            self._state.run(inputs)
