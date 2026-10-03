################################################################################################
#
# Use this as a reference for importing. Instead of "from gameevent import *" use:
#
# from gameevent import GameEvent, SpeechEvent, EventQueue, bulk_speech_event, action_is_bool
#
# IN THIS MODULE:
#
# CLASSES:
#   * GameEvent
#   * SpeechEvent
#   * EventQueue
#
# METHODS:
#   * bulk_speech_event
#   * action_is_bool
#
################################################################################################

import time

# CLEAN THIS UP START#

# Event lifecycle: PENDING -> DONE. An event fires at most once; reset() is a
# configuration-time operation and the only way back to PENDING.
class GameEvent(object):

    event_type = ""

    def __init__(self):
        self.triggered = False
        print("Event created")

    def trigger(self):
        # Fire the event once. Returns True the first time, False afterwards.
        if self.triggered:
            return False
        self.triggered = True
        self.execute()
        return True

    def execute(self):
        # Subclasses override with the event body.
        pass

    def reset(self):
        self.triggered = False

# Dialog and Text Parsing. Wraps the print statement with more functionality.
class SpeechEvent(GameEvent):

    speaker = ""
    message = ""
    sleep = 0

    def __init__(self, speaker, message, sleep = 0):
        GameEvent.__init__(self)
        self.speaker = speaker
        self.message = message
        self.sleep = sleep

    ## Not really necessary but helps cut down on object instances
    ## Modify properties instead of creating new object
    ## As a rule of thumb, you probably shouldn't alter the speaker
    ## unless it's a variant of the original speaker
    ## e.g. Player: to Player(enraged): or something
        
    def set_speaker(self, speaker):
        self.speaker = speaker

    def get_speaker(self):
        print(self.speaker)

    # set_message(self)
    def sm(self, message):
        self.message = message;

    # get_message(self)
    def gm(self):
        if self.speaker == "":
            print(self.message)
            time.sleep(self.sleep)
        else:
            print(self.speaker + ": " + self.message)
            time.sleep(self.sleep)

    def set_sleep(self, sleep):
        self.sleep = sleep

    def execute(self):
        self.gm()

# FIFO queue of GameEvents. Each event may be queued once and fires at most once.
class EventQueue(object):

    def __init__(self):
        self._queue = []

    def enqueue(self, event):
        if not isinstance(event, GameEvent):
            print("CONFIG ERROR: only GameEvent objects can be enqueued.")
            return False
        if event.triggered:
            print("CONFIG ERROR: this event has already fired and cannot be re-queued.")
            return False
        if event in self._queue:
            print("CONFIG ERROR: this event is already queued.")
            return False
        self._queue.append(event)
        return True

    def fire_next(self):
        if not self._queue:
            print("The event queue is empty.")
            return False
        return self._queue.pop(0).trigger()

    def fire_all(self):
        fired = 0
        while self._queue:
            if self.fire_next():
                fired += 1
        return fired

    def pending(self):
        return len(self._queue)

# bulk create SpeechEvents
# You can pass in empty lists for speaker_list and a single sleep value to sleep_list
# and their lists will be created from the length of message_list
def bulk_speech_event(speaker_list, message_list, wait_list):

    new_speaker = []
    new_wait = []

    if type(speaker_list) is str:
        for m in message_list:
            new_speaker.append(speaker_list)
    else:
        new_speaker = speaker_list

    if type(wait_list) is int or type(wait_list) is float:
        for m in message_list:
            new_wait.append(wait_list)
    else:
        new_wait = wait_list
    
    mlist_len = len(message_list)
    
    for x in range(0, mlist_len):
        current = SpeechEvent(new_speaker[x], message_list[x])
        current.gm()
        time.sleep(new_wait[x])

    print()

# Wrapped check to see if player responded true or false
def action_is_bool(input_string, desired_bool):

    if not isinstance(input_string, str):
        return False

    normalized = input_string.strip().lower()

    for db in desired_bool:
        if normalized == db.strip().lower():
            return True

    return False


# CLEAN THIS UP END #

#TESTING
#
##gi_mlist00 = [
##    "HELLO AGAIN",
##    "I SUSPECT I WON'T BE KEEPING YOU LONG TODAY",
##    "YOUR SCORES ARE SUPERB",
##    "AND REPETITION IS AT AN ALL TIME LOW",
##    "//...",
##    "LET US BEGIN",
##    "WHAT IS YOUR NAME?"
##]
##
##bulk_speech_event("", gi_mlist00, 0.5)
