################################################################################################
#
# Use this as a reference for importing. Instead of "from gameconfig import *" use:
#
# from gameconfig import build_floor
#
# IN THIS MODULE:
#
# METHODS:
#   * build_floor
#
################################################################################################

################################################################################################
#
# USAGE
#
# build_floor builds a Floor node tree (Floor -> Rooms) from a plain-dict
# config fragment:
#
# config = {
#     "floor": {"name": "f1", "description": "...", "width": 2, "height": 1,
#               "entrance": (0, 0)},
#     "rooms": [
#         {"name": "r1", "description": "...", "coordinate": (0, 0)},
#         {"name": "r2", "description": "...", "coordinate": (1, 0), "exits": "w"},
#     ],
# }
#
# "exits" is optional; when omitted, exits are derived from the map with
# RoomBase.find_exits(). When given, every declared exit must point at an
# existing neighboring Room.
#
# Config errors never raise exceptions. build_floor returns (floor, errors);
# on any error floor is None and errors is a list of human-readable strings
# telling the designer exactly what to fix.
#
################################################################################################

from floor import Floor
from room import RoomBase

_VALID_EXITS = frozenset("nsew")

def _in_bounds(coordinate, width, height):

    try:
        x, y = coordinate
    except (TypeError, ValueError):
        return False

    return isinstance(x, int) and isinstance(y, int) and 0 <= x < width and 0 <= y < height

def build_floor(config):

    errors = []

    if not isinstance(config, dict):
        return None, ["Config must be a dict, got %s." % type(config).__name__]

    floor_cfg = config.get("floor")

    if not isinstance(floor_cfg, dict):
        return None, ["Config is missing a 'floor' section (a dict with name, width, height, entrance)."]

    for key in ("name", "width", "height", "entrance"):
        if key not in floor_cfg:
            errors.append("Floor config is missing required key '%s'." % key)

    if errors:
        return None, errors

    width = floor_cfg["width"]
    height = floor_cfg["height"]

    if not isinstance(width, int) or not isinstance(height, int) or width <= 0 or height <= 0:
        return None, ["Floor width and height must be positive integers, got %r x %r." % (width, height)]

    entrance = floor_cfg["entrance"]

    if not _in_bounds(entrance, width, height):
        errors.append("Entrance %r is not a valid coordinate on a %dx%d floor." % (entrance, width, height))

    rooms_cfg = config.get("rooms", [])

    if not isinstance(rooms_cfg, list) or not rooms_cfg:
        errors.append("Config defines no rooms; a floor needs at least one room.")
        rooms_cfg = []

    seen_coordinates = {}
    room_entries = []

    for index, room_cfg in enumerate(rooms_cfg):

        label = "room #%d" % index

        if not isinstance(room_cfg, dict):
            errors.append("Room %s must be a dict, got %s." % (label, type(room_cfg).__name__))
            continue

        label = room_cfg.get("name", label)

        if "coordinate" not in room_cfg:
            errors.append("Room '%s' is missing a 'coordinate'." % label)
            continue

        coordinate = room_cfg["coordinate"]

        if not _in_bounds(coordinate, width, height):
            errors.append("Room '%s' coordinate %r is outside the %dx%d floor." % (label, coordinate, width, height))
            continue

        coordinate = tuple(coordinate)

        if coordinate in seen_coordinates:
            errors.append("Rooms '%s' and '%s' share coordinate %s; each room needs its own cell."
                          % (seen_coordinates[coordinate], label, coordinate))
            continue

        exits = room_cfg.get("exits")

        if exits is not None:
            bad_exits = [char for char in exits if char not in _VALID_EXITS]
            if bad_exits:
                errors.append("Room '%s' has invalid exit(s) '%s'; valid exits are n/s/e/w."
                              % (label, "".join(bad_exits)))
                continue

        seen_coordinates[coordinate] = label
        room_entries.append((room_cfg, coordinate))

    if errors:
        return None, errors

    floor = Floor(floor_cfg["name"], floor_cfg.get("description", ""), width, height, tuple(entrance))

    for room_cfg, coordinate in room_entries:
        floor.add_rooms(RoomBase(room_cfg.get("name", "room"), room_cfg.get("description", "")), coordinate)

    for room in floor.children:
        room.find_exits()

    if not isinstance(floor.floor_matrix[tuple(entrance)[0]][tuple(entrance)[1]], RoomBase):
        errors.append("Entrance %s has no room; the player would start on an empty cell." % (tuple(entrance),))

    for room_cfg, coordinate in room_entries:

        declared = room_cfg.get("exits")

        if declared is None:
            continue

        room = floor.floor_matrix[coordinate[0]][coordinate[1]]

        for char in declared:
            if char not in room.exits:
                errors.append("Room '%s' declares exit '%s' but no room lies that way." % (room.name, char))

        room.exits = declared

    if errors:
        return None, errors

    return floor, []
