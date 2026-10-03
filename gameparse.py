################################################################################################
#
# Use this as a reference for importing. Instead of "from gameevent import *" use:
#
# from gameparse import parse_movement, update_floor, update_room
#
# IN THIS MODULE:
#
# CLASSES:
#
# METHODS:
#   * parse_movement
#   * update_floor
#	* update_room
#   * normalize_action
#
################################################################################################

# class GameParse():

#     def someMethod(self):
#         return 3

# Simplify entrance and exit. No exit room; you can ascend any time you like
# Entrance is still necessary as starting point

from room import RoomBase

# action -> (exit character, x delta, y delta, success message, failure message)
MOVEMENT_COMMANDS = {
    "north": ("n", 0, 1, "You head north", "You cannot pass north"),
    "n":     ("n", 0, 1, "You head north", "You cannot pass north"),
    "south": ("s", 0, -1, "You head south", "You cannot pass south"),
    "s":     ("s", 0, -1, "You head south", "You cannot pass south"),
    "east":  ("e", 1, 0, "You head east", "You cannot pass east"),
    "e":     ("e", 1, 0, "You head east", "You cannot pass east"),
    "west":  ("w", -1, 0, "You head west", "You cannot pass west"),
    "w":     ("w", -1, 0, "You head west", "You cannot pass west"),
}

FLOOR_COMMANDS = ("ascend", "elevator")

def normalize_action(action):
    # Parser contract: case, surrounding and repeated internal whitespace are
    # insignificant. Non-string input becomes an empty (unknown) command.
    if not isinstance(action, str):
        return ""
    return " ".join(action.strip().lower().split())

def parse_movement(action, floor_list, floor_index, room_matrix, room_position):

    action = normalize_action(action)

    if not floor_list:
        print("CONFIG ERROR: no floors configured; the game cannot run.")
        return False

    if action == "floor complete":
        floor_list[floor_index[0]].set_goal_complete(True)
        return True

    if action in FLOOR_COMMANDS:
        return update_floor(action, floor_list, floor_index, room_position)

    if action in MOVEMENT_COMMANDS:
        return update_room(action, room_matrix, room_position)

    # Unknown/empty commands short-circuit here: readable message, no state change.
    if action:
        print("Unknown command: '" + action + "'. Try: north, south, east, west, ascend.")
    else:
        print("Unknown command. Try: north, south, east, west, ascend.")
    return False

def update_floor(action, floor_list, floor_index, room_position):

    action = normalize_action(action)
    current_floor = floor_list[floor_index[0]]

    #print("Goal status:", current_floor.get_goal_status())

    if action in FLOOR_COMMANDS:
        if current_floor.goal_complete:

            if floor_index[0] + 1 >= len(floor_list):
                # Top floor: stop instead of indexing off the floor list.
                print("There are no more floors to ascend to.")
                return False

            new_floor = floor_list[floor_index[0] + 1]

            if new_floor.entrance is None:
                print("CONFIG ERROR:", new_floor.name, "has no entrance set. Cannot ascend.")
                return False

            floor_index[0] += 1
            #print(floor_index[0])
            room_position[0] = new_floor.entrance[0]
            room_position[1] = new_floor.entrance[1]
            return True
        else:
            print("The elevator is locked")
            return False

    return False

def update_room(action, room_matrix, room_position):

    action = normalize_action(action)

    if action not in MOVEMENT_COMMANDS:
        return False

    current_room = room_matrix[room_position[0]][room_position[1]]

    if not isinstance(current_room, RoomBase):
        # Empty map cell: there is no room to navigate from.
        print("There is nowhere to go from here.")
        return False

    room_exits = current_room.get_exits()
    exit_char, dx, dy, success_message, fail_message = MOVEMENT_COMMANDS[action]
    new_x = room_position[0] + dx
    new_y = room_position[1] + dy

    # Exit must exist, stay in bounds, and lead to an actual room.
    blocked = (
        exit_char not in room_exits
        or not (0 <= new_x < len(room_matrix) and 0 <= new_y < len(room_matrix[0]))
        or not isinstance(room_matrix[new_x][new_y], RoomBase)
    )

    if blocked:
        print(fail_message)
        return False

    current_room.on_room_exit() # clear room-scoped item state before leaving
    room_position[0] = new_x
    room_position[1] = new_y
    print(success_message)
    room_matrix[new_x][new_y].on_room_enter()
    return True
