from common import EventsRegister
from events.on_ready import on_ready
from events.on_error import on_error
from events.on_command_error import on_command_error


EVENTS_REGISTER: EventsRegister = [
    (on_error, False),
    (on_command_error, False),
    (on_ready, True),
]
