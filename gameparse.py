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
#
################################################################################################

# class GameParse():

#     def someMethod(self):
#         return 3

# Simplify entrance and exit. No exit room; you can ascend any time you like
# Entrance is still necessary as starting point

from room import RoomBase

# Single normalization point for the whole parse chain: leading/trailing
# whitespace stripped, internal whitespace collapsed, case folded. Every
# command comparison must go through this so behavior stays consistent.
def normalize_command(action):

    if not isinstance(action, str):
        return ""

    return " ".join(action.strip().lower().split())

# command -> (exit character, x delta, y delta, printed direction name)
_MOVEMENT_COMMANDS = {
    "north": ("n", 0, 1, "north"),
    "n": ("n", 0, 1, "north"),
    "south": ("s", 0, -1, "south"),
    "s": ("s", 0, -1, "south"),
    "east": ("e", 1, 0, "east"),
    "e": ("e", 1, 0, "east"),
    "west": ("w", -1, 0, "west"),
    "w": ("w", -1, 0, "west"),
}

_FLOOR_COMMANDS = ("ascend", "elevator")

def parse_movement(action, floor_list, floor_index, room_matrix, room_position):

    command = normalize_command(action)

    if command == "floor complete":
        floor_list[floor_index[0]].set_goal_complete(True)
        return True

    if command in _FLOOR_COMMANDS:
        return update_floor(command, floor_list, floor_index, room_position)

    if command in _MOVEMENT_COMMANDS:
        return update_room(command, room_matrix, room_position)

    # Unknown commands short-circuit here: no state changes and a readable
    # message instead of silently falling through both updaters. The next
    # command is still parsed normally (error recovery).
    print("Unknown command:", repr(action), "- try north/south/east/west, ascend or 'floor complete'.")
    return False

def update_floor(action, floor_list, floor_index, room_position):

    command = normalize_command(action)
    current_floor = floor_list[floor_index[0]]

    #print("Goal status:", current_floor.get_goal_status())

    if command in _FLOOR_COMMANDS:

        if not current_floor.goal_complete:
            print("The elevator is locked")
            return False

        if floor_index[0] + 1 >= len(floor_list):
            print("There are no more floors above.")
            return False

        floor_index[0] += 1
        #print(floor_index[0])
        new_floor = floor_list[floor_index[0]]
        room_position[0] = new_floor.entrance[0]
        room_position[1] = new_floor.entrance[1]
        return True

    return False

def update_room(action, room_matrix, room_position):

    command = normalize_command(action)

    if command not in _MOVEMENT_COMMANDS:
        return False

    exit_char, delta_x, delta_y, direction_name = _MOVEMENT_COMMANDS[command]

    current_room = room_matrix[room_position[0]][room_position[1]]
    room_exits = current_room.get_exits()

    if exit_char not in room_exits:
        print("You cannot pass " + direction_name)
        return False

    new_x = room_position[0] + delta_x
    new_y = room_position[1] + delta_y

    if not (0 <= new_x < len(room_matrix)) or not (0 <= new_y < len(room_matrix[0])):
        print("You cannot pass " + direction_name)
        return False

    next_room = room_matrix[new_x][new_y]

    if not isinstance(next_room, RoomBase):
        # The exit table and the map disagree. Recover by staying in place
        # instead of moving onto an empty cell and crashing on it later.
        print("There is no room " + direction_name + " of here.")
        return False

    room_position[0] = new_x
    room_position[1] = new_y

    current_room.on_room_exit()
    next_room.on_room_enter()

    print("You head " + direction_name)
    return True
