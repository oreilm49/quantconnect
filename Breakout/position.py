import datetime
import json
from typing import Optional


class Position:
    start: datetime.datetime
    stop_price: Optional[float]

    def __init__(self, start: datetime.datetime = None, stop_price: float = None) -> None:
        self.start = start
        self.stop_price = stop_price

    def __str__(self) -> str:
        return json.dumps({
            "start": str(self.start),
            "stop_price": self.stop_price
        })


def position_from_str(content: str) -> Position:
    return Position(**json.loads(content))
