import datetime
from dateutil.parser import parse
import json


class Position:
    start: datetime.datetime

    def __init__(self, start: datetime.datetime = None) -> None:
        self.start = start

    def __str__(self) -> str:
        return json.dumps({
            "start": str(self.start),
        })


def position_from_str(content: str) -> Position:
    content = json.loads(content)
    content['start'] = parse(content['start'])
    return Position(**content)
