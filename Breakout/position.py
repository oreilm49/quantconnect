import datetime
from dateutil.parser import parse
import json


class Position:
    """
    Stores information relative to an open position.
    Intended to be persisted in object storage as a json string.
    """
    start: datetime.datetime

    def __init__(self, start: datetime.datetime = None) -> None:
        self.start = start

    def __str__(self) -> str:
        return json.dumps({
            "start": str(self.start),
        })


def position_from_str(content: str) -> Position:
    """
    Method for parsing a Position from object storage.

    Args:
        content (str): the Position content as a json string.

    Returns:
        Position: The position class.
    """
    content = json.loads(content)
    content['start'] = parse(content['start'])
    return Position(**content)
