################################################################################################
#
# Engine tests built from multiple config fragments.
#
# Covered:
#   * loop termination (circular node moves rejected, self-requeueing events
#     cannot loop, ascending past the top floor stops)
#   * error recovery (unknown commands leave state untouched, later commands
#     still work; config errors come back as readable strings)
#   * events fire exactly once (re-entering a room cannot re-trigger)
#   * parser case/whitespace consistency
#   * item transient state is cleared when leaving a room
#
# Run: python3 -m unittest test_engine -v
#
################################################################################################

import io
import unittest
from contextlib import redirect_stdout

from node import Node, node_search, node_move
from leaf import Leaf
from room import RoomBase
from item import Item
from gameevent import GameEvent, SpeechEvent, EventQueue, action_is_bool
from gameparse import parse_movement
from gameconfig import build_floor

# ---------------------------------------------------------------------------
# Config fragments
# ---------------------------------------------------------------------------

CONFIG_CORRIDOR = {  # three rooms in a row, exits derived from the map
    "floor": {"name": "corridor", "description": "test floor", "width": 3, "height": 1, "entrance": (0, 0)},
    "rooms": [
        {"name": "west room", "description": "w", "coordinate": (0, 0)},
        {"name": "mid room", "description": "m", "coordinate": (1, 0)},
        {"name": "east room", "description": "e", "coordinate": (2, 0)},
    ],
}

CONFIG_DECLARED = {  # hand-declared exits that match the map
    "floor": {"name": "declared", "description": "d", "width": 2, "height": 1, "entrance": (0, 0)},
    "rooms": [
        {"name": "r1", "description": "d", "coordinate": (0, 0), "exits": "e"},
        {"name": "r2", "description": "d", "coordinate": (1, 0), "exits": "w"},
    ],
}

CONFIG_BAD_DUPLICATE = {
    "floor": {"name": "dup", "description": "d", "width": 2, "height": 1, "entrance": (0, 0)},
    "rooms": [
        {"name": "r1", "description": "d", "coordinate": (0, 0)},
        {"name": "r2", "description": "d", "coordinate": (0, 0)},
    ],
}

CONFIG_BAD_EXIT_NOWHERE = {
    "floor": {"name": "nowhere", "description": "d", "width": 2, "height": 1, "entrance": (0, 0)},
    "rooms": [
        {"name": "r1", "description": "d", "coordinate": (0, 0), "exits": "e"},
        {"name": "r2", "description": "d", "coordinate": (1, 0), "exits": "n"},
    ],
}

CONFIG_BAD_ENTRANCE = {
    "floor": {"name": "badstart", "description": "d", "width": 2, "height": 2, "entrance": (1, 1)},
    "rooms": [{"name": "r1", "description": "d", "coordinate": (0, 0)}],
}

CONFIG_EMPTY = {
    "floor": {"name": "empty", "description": "d", "width": 1, "height": 1, "entrance": (0, 0)},
    "rooms": [],
}

CONFIG_BAD_EXIT_CHAR = {
    "floor": {"name": "badchar", "description": "d", "width": 1, "height": 1, "entrance": (0, 0)},
    "rooms": [{"name": "r1", "description": "d", "coordinate": (0, 0), "exits": "eq"}],
}

CONFIG_MISSING_KEY = {
    "floor": {"name": "noexit", "width": 1, "height": 1},  # no description needed, but entrance is
    "rooms": [{"name": "r1", "description": "d", "coordinate": (0, 0)}],
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_game(config=CONFIG_CORRIDOR):
    floor, errors = build_floor(config)
    assert not errors, errors
    floor_list = [floor]
    floor_index = [0]
    room_position = [floor.entrance[0], floor.entrance[1]]
    return floor, floor_list, floor_index, floor.floor_matrix, room_position

def run_command(action, floor_list, floor_index, room_matrix, room_position):
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        result = parse_movement(action, floor_list, floor_index, room_matrix, room_position)
    return result, buffer.getvalue()

# ---------------------------------------------------------------------------
# Config fragments -> node tree, readable config errors
# ---------------------------------------------------------------------------

class TestConfigFragments(unittest.TestCase):

    def test_corridor_builds_with_derived_exits(self):
        floor, errors = build_floor(CONFIG_CORRIDOR)
        self.assertEqual(errors, [])
        self.assertEqual(floor.floor_matrix[0][0].exits, "e")
        self.assertEqual(floor.floor_matrix[1][0].exits, "ew")
        self.assertEqual(floor.floor_matrix[2][0].exits, "w")

    def test_declared_exits_are_kept(self):
        floor, errors = build_floor(CONFIG_DECLARED)
        self.assertEqual(errors, [])
        self.assertEqual(floor.floor_matrix[0][0].exits, "e")
        self.assertEqual(floor.floor_matrix[1][0].exits, "w")

    def test_config_errors_are_readable(self):
        bad_configs = [
            CONFIG_BAD_DUPLICATE,
            CONFIG_BAD_EXIT_NOWHERE,
            CONFIG_BAD_ENTRANCE,
            CONFIG_EMPTY,
            CONFIG_BAD_EXIT_CHAR,
            CONFIG_MISSING_KEY,
            "not a dict",
        ]
        for config in bad_configs:
            floor, errors = build_floor(config)
            self.assertIsNone(floor)
            self.assertTrue(errors, "expected errors for %r" % (config,))
            for error in errors:
                self.assertIsInstance(error, str)
                self.assertTrue(error.strip())

    def test_config_errors_name_the_problem(self):
        _, errors = build_floor(CONFIG_BAD_DUPLICATE)
        self.assertIn("coordinate", errors[0])
        _, errors = build_floor(CONFIG_BAD_EXIT_NOWHERE)
        self.assertIn("exit", errors[0])
        _, errors = build_floor(CONFIG_MISSING_KEY)
        self.assertIn("entrance", errors[0])

# ---------------------------------------------------------------------------
# Loop termination: circular node moves, self-requeueing events, top floor
# ---------------------------------------------------------------------------

class TestLoopTermination(unittest.TestCase):

    def test_circular_reparent_is_rejected(self):
        node_a = Node("a", "node a")
        node_b = Node("b", "node b")
        node_c = Node("c", "node c")
        node_a.add_children(node_b)
        node_b.add_children(node_c)

        with redirect_stdout(io.StringIO()):
            moved = node_move(node_a, node_c)  # a under its own descendant

        self.assertFalse(moved)
        self.assertIsNone(node_a.parent)       # tree unchanged
        self.assertEqual(node_b.children, [node_c])
        self.assertEqual(node_a.children, [node_b])

    def test_self_reparent_is_rejected(self):
        node_a = Node("a", "node a")
        with redirect_stdout(io.StringIO()):
            self.assertFalse(node_move(node_a, node_a))
        self.assertIsNone(node_a.parent)
        self.assertEqual(node_a.children, [])

    def test_legal_move_still_works(self):
        node_a = Node("a", "node a")
        node_b = Node("b", "node b")
        leaf = Leaf("leaf", "a leaf")
        node_b.add_children(leaf)
        self.assertTrue(node_move(leaf, node_a))
        self.assertIs(leaf.parent, node_a)
        self.assertEqual(node_b.children, [])

    def test_self_requeueing_event_terminates(self):

        class RequeueEvent(GameEvent):
            def __init__(self, queue):
                GameEvent.__init__(self)
                self.queue = queue
                self.fires = 0

            def fire(self):
                self.fires += 1
                self.queue.enqueue(self)  # must be rejected: already FIRED

        queue = EventQueue()
        event = RequeueEvent(queue)

        with redirect_stdout(io.StringIO()):
            queue.enqueue(event)
            fired = queue.fire_all()

        self.assertEqual(len(fired), 1)
        self.assertEqual(event.fires, 1)
        self.assertEqual(len(queue), 0)

    def test_ascend_stops_at_top_floor(self):
        floor1, errors1 = build_floor(CONFIG_CORRIDOR)
        floor2, errors2 = build_floor(CONFIG_DECLARED)
        self.assertEqual(errors1 + errors2, [])

        floor_list = [floor1, floor2]
        floor_index = [0]
        position = [0, 0]

        _, out = run_command("ascend", floor_list, floor_index, floor1.floor_matrix, position)
        self.assertIn("The elevator is locked", out)
        self.assertEqual(floor_index[0], 0)

        run_command("floor complete", floor_list, floor_index, floor1.floor_matrix, position)
        result, _ = run_command("ascend", floor_list, floor_index, floor1.floor_matrix, position)
        self.assertTrue(result)
        self.assertEqual(floor_index[0], 1)
        self.assertEqual(position, list(floor2.entrance))

        run_command("floor complete", floor_list, floor_index, floor2.floor_matrix, position)
        result, out = run_command("ascend", floor_list, floor_index, floor2.floor_matrix, position)
        self.assertFalse(result)
        self.assertIn("no more floors", out)
        self.assertEqual(floor_index[0], 1)  # index did not run away

# ---------------------------------------------------------------------------
# Error recovery: unknown commands, empty nodes, exit/map mismatch
# ---------------------------------------------------------------------------

class TestErrorRecovery(unittest.TestCase):

    def test_unknown_command_recovers(self):
        floor, floor_list, floor_index, matrix, position = make_game()

        result, out = run_command("dance", floor_list, floor_index, matrix, position)
        self.assertFalse(result)
        self.assertIn("Unknown command", out)
        self.assertEqual(position, [0, 0])  # state untouched

        result, _ = run_command("east", floor_list, floor_index, matrix, position)
        self.assertTrue(result)             # parser still works afterwards
        self.assertEqual(position, [1, 0])

    def test_empty_and_none_commands_are_safe(self):
        floor, floor_list, floor_index, matrix, position = make_game()
        for bad_input in ("", "   ", None, 42):
            result, out = run_command(bad_input, floor_list, floor_index, matrix, position)
            self.assertFalse(result)
            self.assertIn("Unknown command", out)
        self.assertEqual(position, [0, 0])

    def test_blocked_exit_does_not_move(self):
        floor, floor_list, floor_index, matrix, position = make_game()
        result, out = run_command("west", floor_list, floor_index, matrix, position)
        self.assertFalse(result)
        self.assertIn("You cannot pass west", out)
        self.assertEqual(position, [0, 0])

    def test_exit_pointing_at_empty_cell_recovers(self):
        # A stale exit table says "e" but the cell holds no Room.
        floor, floor_list, floor_index, matrix, position = make_game()
        matrix[1][0] = False  # corrupt the map after exits were derived
        result, out = run_command("east", floor_list, floor_index, matrix, position)
        self.assertFalse(result)
        self.assertIn("no room", out)
        self.assertEqual(position, [0, 0])

    def test_empty_node_guards(self):
        empty = Node("empty", "an empty node")
        with redirect_stdout(io.StringIO()):
            self.assertIsNone(node_search("ghost", empty))   # search empty node
            self.assertFalse(empty.add_children([]))         # empty child list
            self.assertFalse(empty.add_children(None))       # None child
            self.assertFalse(empty.remove_children(Leaf("x", "not a child")))
        self.assertEqual(empty.children, [])

    def test_detached_room_find_exits_does_not_crash(self):
        room = RoomBase("lonely", "not on any floor")
        with redirect_stdout(io.StringIO()) as buffer:
            room.find_exits()
        self.assertIn("DEBUG", buffer.getvalue())
        self.assertEqual(room.exits, "")

    def test_node_search_handles_room_contents(self):
        room = RoomBase("vault", "a vault")
        item = Item("key", "a brass key")
        room.add_contents(item, "pickups")
        with redirect_stdout(io.StringIO()):
            self.assertIs(node_search("key", room), item)
            self.assertIsNone(node_search("ghost", room))

# ---------------------------------------------------------------------------
# Events fire exactly once
# ---------------------------------------------------------------------------

class TestEventsFireOnce(unittest.TestCase):

    def test_room_event_fires_once_across_reentries(self):
        floor, floor_list, floor_index, matrix, position = make_game()
        mid_room = matrix[1][0]
        mid_room.events.append(SpeechEvent("Guide", "Welcome to the middle."))

        run_command("east", floor_list, floor_index, matrix, position)   # enter mid
        run_command("west", floor_list, floor_index, matrix, position)   # leave
        _, out = run_command("east", floor_list, floor_index, matrix, position)  # re-enter

        self.assertNotIn("Guide: Welcome to the middle.", out)  # no re-trigger
        self.assertTrue(mid_room.events[0].triggered)

    def test_trigger_returns_true_only_once(self):
        event = GameEvent()
        with redirect_stdout(io.StringIO()):
            self.assertTrue(event.trigger())
            self.assertFalse(event.trigger())
            event.reset()
            self.assertTrue(event.trigger())

    def test_queue_rejects_duplicates(self):
        queue = EventQueue()
        event = GameEvent()
        with redirect_stdout(io.StringIO()):
            self.assertTrue(queue.enqueue(event))
            self.assertFalse(queue.enqueue(event))
        self.assertEqual(len(queue), 1)

    def test_action_is_bool_normalizes(self):
        self.assertTrue(action_is_bool("  YES ", ["yes"]))
        self.assertTrue(action_is_bool("Y", ["no", "y"]))  # checks every entry
        self.assertFalse(action_is_bool("maybe", ["yes", "no"]))

# ---------------------------------------------------------------------------
# Parser case/whitespace consistency
# ---------------------------------------------------------------------------

class TestParserNormalization(unittest.TestCase):

    def test_case_and_whitespace_variants_move_identically(self):
        for command in ("east", "EAST", " East ", "e", "E", "\te\n"):
            floor, floor_list, floor_index, matrix, position = make_game()
            result, out = run_command(command, floor_list, floor_index, matrix, position)
            self.assertTrue(result, command)
            self.assertEqual(position, [1, 0], command)
            self.assertIn("You head east", out)

    def test_multiword_command_with_extra_whitespace(self):
        floor, floor_list, floor_index, matrix, position = make_game()
        result, _ = run_command("  Floor   Complete ", floor_list, floor_index, matrix, position)
        self.assertTrue(result)
        self.assertTrue(floor.goal_complete)

# ---------------------------------------------------------------------------
# Item transient state is cleared when leaving a room
# ---------------------------------------------------------------------------

class TestItemStateCleanup(unittest.TestCase):

    def test_transient_state_cleared_on_room_exit(self):
        floor, floor_list, floor_index, matrix, position = make_game()
        west_room = matrix[0][0]
        item = Item("scrap metal", "a refined sheet of metal")
        west_room.add_contents(item, "pickups")

        item.transient_state["searched"] = True  # per-visit state

        result, _ = run_command("east", floor_list, floor_index, matrix, position)
        self.assertTrue(result)
        self.assertEqual(item.transient_state, {})  # cleaned up on exit
        self.assertIs(item.parent, west_room)       # item itself stays put

    def test_permanent_state_survives_room_exit(self):
        floor, floor_list, floor_index, matrix, position = make_game()
        west_room = matrix[0][0]
        item = Item("scrap metal", "a refined sheet of metal")
        west_room.add_contents(item, "pickups")
        item.name = "polished scrap"  # permanent change

        run_command("east", floor_list, floor_index, matrix, position)
        self.assertEqual(item.name, "polished scrap")

if __name__ == "__main__":
    unittest.main()
