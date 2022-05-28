import csv
import datetime
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd


@dataclass
class Position:
    start: datetime.datetime
    end: Optional[datetime.datetime]
    symbol: str
    price: float
    size: float
    type: str
    status: str
    value: float
    quantity_sold: float
    profit: float

    @property
    def liquidated(self) -> bool:
        return (self.size - self.quantity_sold) == 0

    def sell(self, data: pd.Series) -> None:
        self.quantity_sold += data.Quantity
        self.profit += (data.Value * -1)

    def add(self, data: pd.Series) -> None:
        self.value += data.Value
        self.size += data.Quantity
        self.price = self.value / self.size

    def __getitem__(self, key):
        return getattr(self, key)

    def keys(self):
        return 'start', 'end', 'symbol', 'price', 'size', 'type', 'status', 'value', 'quantity_sold', 'profit',


def analyze_orders() -> None:
    folder_path = ""
    files = os.listdir(folder_path)
    for filename in files:
        name, ending = filename.split(".")
        analyzed_filename = f"{name}_analyzed.csv"
        if ending == 'csv' and analyzed_filename not in files:
            orders = pd.read_csv(Path(folder_path, filename))
            open_positions: dict[str, Position] = {}
            closed_positions: list[Position] = []
            for index, data in orders[orders.Status == 'Filled'].iterrows():
                if data.Quantity < 0:
                    open_positions[data.Symbol].sell(data)
                    if open_positions[data.Symbol].liquidated:
                        closed_positions.append(open_positions.pop(data.Symbol))
                else:
                    if data.Symbol not in open_positions:
                        open_positions[data.Symbol] = Position(
                            start=index,
                            end=None,
                            symbol=data.Symbol,
                            price=data.Price,
                            size=data.Quantity,
                            type=data.Type,
                            status=data.Status,
                            value=data.Value,
                            quantity_sold=0,
                            profit=0,
                        )
                    else:
                        open_positions[data.Symbol].add(data)
            if not closed_positions and not open_positions:
                continue
            with open(f"{folder_path}/{analyzed_filename}", 'w', encoding='UTF8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=closed_positions[0].keys())
                writer.writeheader()
                writer.writerows(closed_positions)
