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
    value: float
    quantity_sold: float
    value_sold: float

    @property
    def liquidated(self) -> bool:
        return self.size == self.quantity_sold

    def sell(self, data: pd.Series) -> None:
        self.quantity_sold += (data.Quantity * -1)
        self.value_sold += (data.Value * -1)

    def add(self, data: pd.Series) -> None:
        self.value += data.Value
        self.size += data.Quantity
        self.price = self.value / self.size

    @property
    def profit(self) -> float:
        return self.value_sold - self.value

    @property
    def profit_pc(self) -> float:
        return (self.profit / self.value_sold) * 100 if self.value_sold else 0

    @property
    def days(self) -> Optional[int]:
        return (self.end - self.start).days if self.end else "-"

    def close(self, data: pd.Series) -> None:
        self.end = data.Time

    def get_values(self, names: list[str]):
        return [getattr(self, name) for name in names]


def analyze_orders() -> None:
    folder_path = Path(Path().absolute(), 'backtest_reports')
    files = os.listdir(folder_path)
    for filename in files:
        name, ending = filename.split(".")
        if ending == 'csv' and '_analyzed' not in name:
            orders = pd.read_csv(Path(folder_path, filename))
            orders['Time'] = pd.to_datetime(orders['Time'])
            open_positions: dict[str, Position] = {}
            closed_positions: list[Position] = []
            for index, data in orders[orders.Status == 'Filled'].iterrows():
                if data.Quantity < 0:
                    open_positions[data.Symbol].sell(data)
                    if open_positions[data.Symbol].liquidated:
                        open_positions[data.Symbol].close(data)
                        closed_positions.append(open_positions.pop(data.Symbol))
                else:
                    if data.Symbol not in open_positions:
                        open_positions[data.Symbol] = Position(
                            start=data.Time,
                            end=None,
                            symbol=data.Symbol,
                            price=data.Price,
                            size=data.Quantity,
                            value=data.Value,
                            quantity_sold=0,
                            value_sold=0,
                        )
                    else:
                        open_positions[data.Symbol].add(data)
            positions = [*closed_positions, *open_positions.values()]
            if not positions:
                continue
            with open(Path(folder_path, f"{name}_analyzed.csv"), 'w', encoding='UTF8', newline='') as f:
                writer = csv.writer(f)
                headers = ['start', 'end', 'symbol', 'price', 'size', 'value', 'quantity_sold', 'value_sold', 'profit', 'profit_pc', 'days']
                writer.writerow(headers)
                position: Position
                for position in positions:
                    writer.writerow(position.get_values(headers))


if __name__ == "__main__":
    analyze_orders()
