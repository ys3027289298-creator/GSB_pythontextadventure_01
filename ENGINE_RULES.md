# Engine rules: legal transitions and error contract

This file defines the legal state transitions for the node tree and the event
queue, plus the parser/config error contract. These are the invariants the
engine code and tests rely on.

## 1. Node tree

Invariants

- Every `Node`/`Leaf` has at most one parent; `child.parent` points back to
  exactly the `Node` whose `children` collection contains it.
- The parent chain is acyclic; walking `node.parent` always terminates at
  `None`.
- An empty node is legal; searches over an empty node return `None` with a
  readable message instead of raising.

Legal transitions

- **Add child**: parent `P`, child `C`; legal only if `C` is a `Node`/`Leaf`,
  `C is not P`, and `C` is not already an ancestor of `P` (no cycle). If `C`
  has another parent it is detached first, so the one-parent invariant holds.
- **Remove child**: legal only if `C` is actually a child of `P`.
- **Reparent/move** (`reparent`, `node_move`): atomic remove-then-add to a new
  `Node` parent. Rejected (state unchanged) when the destination is not a
  `Node`, when it is the node itself, or when it is a descendant (circular
  jump). Moving to the current parent is a no-op.
- All of the above return `True`/`False` and print a readable
  `CONFIG ERROR: ...` message on rejection.

`RoomBase.children` is the categorized dict
`{'creatures': [], 'pickups': [], 'features': []}`; `node_search` transparently
searches every category.

## 2. Event queue

Event lifecycle

- States: `PENDING -> DONE`. `trigger()` runs an event at most once: the first
  call runs the event body and returns `True`; later calls are no-ops and
  return `False`.
- `reset()` is the only way back to `PENDING` and is a configuration-time
  operation, never triggered during normal play (prevents duplicate triggers).

`EventQueue`

- FIFO. `enqueue` accepts only `GameEvent` objects; an event already queued or
  already `DONE` is rejected.
- `fire_next`/`fire_all` drain the queue; each event fires at most once.

## 3. Room entry/exit

- Moving between rooms runs `current_room.on_room_exit()` before the move and
  `next_room.on_room_enter()` after it.
- `on_room_exit` calls `reset_transient_state()` on every room content, which
  restores attributes named in a `Leaf`/`Node` subclass `transient_attributes`
  tuple to their class-level defaults. Room-scoped item state therefore cannot
  leak out of the room it was set in.

## 4. Parser contract

- Input is normalized exactly once per command:
  `" ".join(action.strip().lower().split())` (case, leading/trailing and
  repeated internal whitespace are insignificant). Non-string input is treated
  as an empty command.
- A command dispatches to exactly one handler: movement (`north/n`, ...),
  floor (`ascend`/`elevator`), or `floor complete`.
- Unknown or empty commands short-circuit immediately: they print a readable
  message, change no state, and return `False`, so the next command still
  works (error recovery).
- Walking into a missing exit, a blank map cell, or past the edge of the
  matrix prints the standard "cannot pass" message and leaves position
  unchanged. Ascending past the last floor prints a readable message instead
  of indexing off the floor list (loop termination).

## 5. Configuration errors

Configuration errors (bad types, out-of-bounds coordinates, length-mismatched
room/coordinate lists, circular parenting, duplicate/invalid contents, invalid
goal values) must:

1. print a single human-readable message (`CONFIG ERROR: ...` for engine-level
   checks; the existing coordinate messages in `floor.py`),
2. leave the game state unchanged (no half-applied transition),
3. return `False` where a boolean result is available.
