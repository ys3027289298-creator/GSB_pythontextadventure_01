################################################################################################
#
# Engine tests. Run with: python3 -m unittest test_engine -v
#
# Each test class builds its own small configuration fragment (floors/rooms/
# nodes/events) so the contracts in ENGINE_RULES.md are verified in isolation:
# loop termination, error recovery, fire-once events, transient item cleanup
# and readable configuration errors.
#
################################################################################################

import io
import unittest
from contextlib import redirect_stdout

# floor.py builds a demo FloorRandom at import time; swallow that output.
with redirect_stdout(io.StringIO()):
    from node import Node, node_search, node_move
    from leaf import Leaf
    from room import RoomBase
    from floor import Floor
    from gameevent import GameEvent, SpeechEvent, EventQueue, action_is_bool
    from gameparse import parse_movement


def run(func, *args):
    """Call func, capturing printed output. Returns (result, output)."""
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        result = func(*args)
    return result, buffer.getvalue()


# ---------------------------------------------------------------------------
# Configuration fragments
# ---------------------------------------------------------------------------

def fragment_tower():
    """Two floors. Floor 1: West Room -(e)-> East Room. Floor 2: single room."""
    room_w = RoomBase("West Room", "The west room", "e")
    room_e = RoomBase("East Room", "The east room", "w")
    floor1 = Floor("Floor 1", "The first floor", 2, 1, (0, 0))
    floor1.add_rooms([room_w, room_e], [(0, 0), (1, 0)])

    room_top = RoomBase("Top Room", "The only room upstairs")
    floor2 = Floor("Floor 2", "The top floor", 1, 1, (0, 0))
    floor2.add_rooms(room_top, (0, 0))

    floors = [floor1, floor2]
    return floors, [0], [0, 0], room_w, room_e


def fragment_node_chain():
    """Plain node chain a -> b -> c (c is a child of b, b of a)."""
    a = Node("a", "node a")
    b = Node("b", "node b")
    c = Node("c", "node c")
    b.set_parent(a)
    c.set_parent(b)
    return a, b, c


class Torch(Leaf):
    transient_attributes = ("lit",)
    lit = False  # class-level default restored on room exit


class CounterEvent(GameEvent):
    def __init__(self):
        GameEvent.__init__(self)
        self.count = 0

    def execute(self):
        self.count += 1


# ---------------------------------------------------------------------------
# Parser: case/whitespace normalization
# ---------------------------------------------------------------------------

class TestParserNormalization(unittest.TestCase):

    def test_movement_ignores_case_and_whitespace(self):
        floors, floor_index, position, _, _ = fragment_tower()
        result, output = run(parse_movement, "  EaSt\t", floors, floor_index, floors[0].floor_matrix, position)
        self.assertTrue(result)
        self.assertIn("You head east", output)
        self.assertEqual(position, [1, 0])

    def test_internal_whitespace_and_case_in_multiword_command(self):
        floors, floor_index, position, _, _ = fragment_tower()
        result, _ = run(parse_movement, "  FLOOR   Complete ", floors, floor_index, floors[0].floor_matrix, position)
        self.assertTrue(result)
        self.assertTrue(floors[0].goal_complete)

    def test_action_is_bool_normalizes_and_checks_all_options(self):
        self.assertTrue(action_is_bool("YES", ["yes"]))
        self.assertTrue(action_is_bool("  Y ", ["yes", "y"]))  # match is the 2nd option
        self.assertFalse(action_is_bool("maybe", ["yes", "y"]))
        self.assertFalse(action_is_bool(None, ["yes"]))


# ---------------------------------------------------------------------------
# Unknown commands: short-circuit and error recovery
# ---------------------------------------------------------------------------

class TestUnknownCommandRecovery(unittest.TestCase):

    def test_unknown_command_changes_nothing_and_game_continues(self):
        floors, floor_index, position, _, _ = fragment_tower()
        result, output = run(parse_movement, "dance", floors, floor_index, floors[0].floor_matrix, position)
        self.assertFalse(result)
        self.assertIn("Unknown command", output)
        self.assertEqual(position, [0, 0])

        # Error recovery: the next valid command still works.
        result, output = run(parse_movement, "east", floors, floor_index, floors[0].floor_matrix, position)
        self.assertTrue(result)
        self.assertEqual(position, [1, 0])

    def test_empty_and_non_string_input(self):
        floors, floor_index, position, _, _ = fragment_tower()
        for bad in ("   ", None, 42):
            result, output = run(parse_movement, bad, floors, floor_index, floors[0].floor_matrix, position)
            self.assertFalse(result)
            self.assertIn("Unknown command", output)
            self.assertEqual(position, [0, 0])

    def test_blocked_exit_keeps_position(self):
        floors, floor_index, position, _, _ = fragment_tower()
        result, output = run(parse_movement, "north", floors, floor_index, floors[0].floor_matrix, position)
        self.assertFalse(result)
        self.assertIn("You cannot pass north", output)
        self.assertEqual(position, [0, 0])


# ---------------------------------------------------------------------------
# Circular jumps and loop termination
# ---------------------------------------------------------------------------

class TestCircularJumps(unittest.TestCase):

    def test_reparent_into_own_descendant_is_rejected(self):
        a, b, c = fragment_node_chain()
        result, output = run(a.reparent, c)
        self.assertFalse(result)
        self.assertIn("circular", output)
        self.assertIsNone(a.parent)      # tree unchanged
        self.assertEqual(c.children, [])  # no half-applied move

    def test_reparent_into_self_is_rejected(self):
        a, _, _ = fragment_node_chain()
        result, output = run(a.reparent, a)
        self.assertFalse(result)
        self.assertIn("circular", output)

    def test_node_move_validates_target_and_destination(self):
        a, b, _ = fragment_node_chain()
        result, output = run(node_move, a, "not a node")
        self.assertFalse(result)
        self.assertIn("CONFIG ERROR", output)
        result, output = run(node_move, a, b)  # b is a's descendant
        self.assertFalse(result)
        self.assertIn("circular", output)

    def test_legal_reparent_still_works(self):
        a, b, c = fragment_node_chain()
        result, _ = run(c.reparent, a)
        self.assertTrue(result)
        self.assertIn(c, a.children)
        self.assertEqual(b.children, [])
        self.assertIs(c.parent, a)

    def test_ascend_past_top_floor_terminates(self):
        floors, floor_index, position, _, _ = fragment_tower()
        run(parse_movement, "floor complete", floors, floor_index, floors[0].floor_matrix, position)
        result, _ = run(parse_movement, "ascend", floors, floor_index, floors[0].floor_matrix, position)
        self.assertTrue(result)
        self.assertEqual(floor_index, [1])
        self.assertEqual(position, [0, 0])  # entrance of floor 2

        # Top floor: ascending again must stop, not index off the list.
        run(parse_movement, "floor complete", floors, floor_index, floors[1].floor_matrix, position)
        result, output = run(parse_movement, "ascend", floors, floor_index, floors[1].floor_matrix, position)
        self.assertFalse(result)
        self.assertIn("no more floors", output)
        self.assertEqual(floor_index, [1])

    def test_locked_elevator(self):
        floors, floor_index, position, _, _ = fragment_tower()
        result, output = run(parse_movement, "ascend", floors, floor_index, floors[0].floor_matrix, position)
        self.assertFalse(result)
        self.assertIn("The elevator is locked", output)
        self.assertEqual(floor_index, [0])


# ---------------------------------------------------------------------------
# Events fire exactly once
# ---------------------------------------------------------------------------

class TestEventsFireOnce(unittest.TestCase):

    def test_speech_event_fires_once(self):
        event = SpeechEvent("NPC", "Hello there")
        run(event.trigger)
        _, output = run(event.trigger)
        self.assertNotIn("Hello there", output)  # second trigger is a no-op
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            event.reset()
            event.trigger()
        self.assertEqual(buffer.getvalue().count("NPC: Hello there"), 1)

    def test_game_event_execute_runs_once(self):
        event = CounterEvent()
        run(event.trigger)
        run(event.trigger)
        self.assertEqual(event.count, 1)
        run(event.reset)
        run(event.trigger)
        self.assertEqual(event.count, 2)  # reset() is the only way back to PENDING

    def test_event_queue_fifo_and_no_double_fire(self):
        first, second = CounterEvent(), CounterEvent()
        queue = EventQueue()
        self.assertTrue(run(queue.enqueue, first)[0])
        self.assertTrue(run(queue.enqueue, second)[0])

        result, output = run(queue.enqueue, first)  # already queued
        self.assertFalse(result)
        self.assertIn("CONFIG ERROR", output)

        fired, _ = run(queue.fire_all)
        self.assertEqual(fired, 2)
        self.assertEqual((first.count, second.count), (1, 1))

        result, output = run(queue.enqueue, first)  # already fired
        self.assertFalse(result)
        self.assertIn("CONFIG ERROR", output)

        result, output = run(queue.fire_next)  # drained queue
        self.assertFalse(result)
        self.assertIn("empty", output)

    def test_event_queue_rejects_non_events(self):
        result, output = run(EventQueue().enqueue, "not an event")
        self.assertFalse(result)
        self.assertIn("CONFIG ERROR", output)


# ---------------------------------------------------------------------------
# Transient item state is cleaned when leaving a room
# ---------------------------------------------------------------------------

class TestItemStateCleanup(unittest.TestCase):

    def test_transient_state_resets_on_room_exit(self):
        floors, floor_index, position, room_w, _ = fragment_tower()
        torch = Torch("torch", "A torch")
        room_w.add_contents(torch, "pickups")

        torch.lit = True  # set while inside the room
        result, _ = run(parse_movement, "east", floors, floor_index, floors[0].floor_matrix, position)
        self.assertTrue(result)
        self.assertFalse(torch.lit)  # cleaned on the way out

    def test_permanent_attributes_survive_room_exit(self):
        floors, floor_index, position, room_w, _ = fragment_tower()
        torch = Torch("torch", "A torch")
        room_w.add_contents(torch, "pickups")
        torch.description = "A well-used torch"  # not transient
        run(parse_movement, "east", floors, floor_index, floors[0].floor_matrix, position)
        self.assertEqual(torch.description, "A well-used torch")


# ---------------------------------------------------------------------------
# Empty nodes and empty map cells
# ---------------------------------------------------------------------------

class TestEmptyNodes(unittest.TestCase):

    def test_search_empty_node(self):
        result, output = run(node_search, "anything", Node("empty", "nothing here"))
        self.assertIsNone(result)
        self.assertIn("empty", output)

    def test_search_room_dict_children(self):
        room = RoomBase("Room", "A room")
        torch = Torch("torch", "A torch")
        room.add_contents(torch, "pickups")
        self.assertIs(node_search("torch", room), torch)
        result, output = run(node_search, "missing", room)
        self.assertIsNone(result)
        self.assertIn("not found", output.lower())

    def test_movement_from_blank_map_cell(self):
        floor = Floor("Sparse", "Mostly empty", 2, 2, (0, 0))
        floor.add_rooms(RoomBase("Only Room", "The only room", ""), (0, 0))
        position = [1, 1]  # blank cell, no room here
        result, output = run(parse_movement, "north", [floor], [0], floor.floor_matrix, position)
        self.assertFalse(result)
        self.assertIn("nowhere to go", output)
        self.assertEqual(position, [1, 1])


# ---------------------------------------------------------------------------
# Readable configuration errors
# ---------------------------------------------------------------------------

class TestReadableConfigErrors(unittest.TestCase):

    def test_room_coordinate_out_of_bounds(self):
        floor = Floor("F", "A floor", 2, 2, (0, 0))
        _, output = run(floor.add_rooms, RoomBase("R", "A room"), (9, 9))
        self.assertIn("does not exist", output)
        self.assertEqual(floor.children, [])  # state unchanged

    def test_room_coordinate_list_length_mismatch(self):
        floor = Floor("F", "A floor", 2, 2, (0, 0))
        rooms = [RoomBase("R1", "r1"), RoomBase("R2", "r2")]
        _, output = run(floor.add_rooms, rooms, [(0, 0)])
        self.assertIn("Could not add rooms", output)
        self.assertEqual(floor.children, [])

    def test_add_children_rejects_bad_input(self):
        node = Node("n", "a node")
        for bad in ("a string", [], None, 42):
            result, output = run(node.add_children, bad)
            self.assertFalse(result)
            self.assertIn("CONFIG ERROR", output)
            self.assertEqual(node.children, [])

    def test_remove_children_rejects_non_child(self):
        node = Node("n", "a node")
        stranger = Leaf("stranger", "not a child")
        result, output = run(node.remove_children, stranger)
        self.assertFalse(result)
        self.assertIn("CONFIG ERROR", output)

    def test_room_rejects_unknown_content_category(self):
        room = RoomBase("Room", "A room")
        result, output = run(room.add_contents, Torch("t", "a torch"), "bogus")
        self.assertFalse(result)
        self.assertIn("CONFIG ERROR", output)

    def test_goal_complete_rejects_non_boolean(self):
        floor = Floor("F", "A floor", 1, 1, (0, 0))
        _, output = run(floor.set_goal_complete, "yes")
        self.assertIn("CONFIG ERROR", output)
        self.assertFalse(floor.goal_complete)

    def test_ascend_to_floor_without_entrance(self):
        floors, floor_index, position, _, _ = fragment_tower()
        broken = Floor("Broken", "Entrance out of bounds", 1, 1, (5, 5))
        floors.append(broken)
        run(parse_movement, "floor complete", floors, floor_index, floors[0].floor_matrix, position)
        run(parse_movement, "ascend", floors, floor_index, floors[0].floor_matrix, position)
        self.assertEqual(floor_index, [1])
        run(parse_movement, "floor complete", floors, floor_index, floors[1].floor_matrix, position)
        result, output = run(parse_movement, "ascend", floors, floor_index, floors[1].floor_matrix, position)
        self.assertFalse(result)
        self.assertIn("CONFIG ERROR", output)
        self.assertEqual(floor_index, [1])  # no half-applied ascend

    def test_parse_movement_without_floors(self):
        result, output = run(parse_movement, "north", [], [0], [], [0, 0])
        self.assertFalse(result)
        self.assertIn("CONFIG ERROR", output)


if __name__ == "__main__":
    unittest.main()
