# Legal Transitions: Node Tree and Event Queue

This document defines the only legal state transitions the engine performs.
`room`, `node`, `leaf`, `gameevent` and `gameparse` must preserve these
invariants; illegal transitions are rejected with a readable message and leave
all state unchanged.

## Node tree (`node.py`, `leaf.py`, `room.py`, `floor.py`)

Each `Node`/`Leaf` is either DETACHED (`parent is None`) or ATTACHED to one
parent.

1. attach: DETACHED -> ATTACHED(p) via `add_children` / `set_parent`.
   Legal only when p is a Node, the child is not p itself, and p is not a
   descendant of the child (no circular parent chain).
2. move: ATTACHED(p) -> ATTACHED(q) via `reparent` / `node_move`.
   Atomic: the child is fully removed from p and added to q, or nothing
   changes. Moving to the current parent is a no-op.
3. detach: ATTACHED(p) -> DETACHED via `remove_children` / `reset_parent`.

Invariants:

- Every node has at most one parent; adding an already-parented child first
  detaches it from the old parent.
- `parent` and `children` references are always consistent in both directions.
- The parent chain is acyclic and a child appears at most once.
- A `Leaf` is never a parent (only Nodes accept children).
- Empty/None/non-node children are rejected, never silently accepted.

## Event queue (`gameevent.py`)

Each event has the state NEW -> QUEUED -> FIRED; FIRED -> NEW only through an
explicit `reset()` (this never happens automatically).

1. enqueue: NEW -> QUEUED. Duplicate events and already-fired events are
   rejected.
2. fire: QUEUED -> FIRED. Exactly-once: calling `trigger()` on a FIRED event
   is a no-op that returns False.
3. reset: FIRED -> NEW. Explicit only.

Termination guarantee: `EventQueue.fire_all()` always terminates because a
fired event cannot re-enter the queue without `reset()`, so an event that
re-enqueues itself cannot create an infinite loop.

## Command dispatch (`gameparse.py`)

Raw input goes through a single normalization step (`strip`, collapse inner
whitespace, `lower`). It then matches exactly one branch: floor commands,
movement commands, or the unknown-command branch. Unknown commands print a
readable message, change no state, and the next command is still processed
(error recovery).
