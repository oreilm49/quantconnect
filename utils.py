import os, csv


def process_orders(path) -> None:
    open_positions_map = {}
    positions = []
    with open(path, newline='') as csvfile:
        for row in csv.DictReader(csvfile):
            if row['Status'] == 'Invalid':
                continue
            if row['Symbol'] not in open_positions_map:
                open_positions_map[row['Symbol']] = {
                    'start': row['Date Time'],
                    'symbol': row['Symbol'],
                    'entry': row['Price'],
                    'size': row['Quantity'],
                }
            else:
                positions.append({
                    **open_positions_map[row['Symbol']],
                    'exit': row['Price'],
                    'end': row['Date Time'],
                })
                open_positions_map.pop(row['Symbol'])
    with open(path.replace(".csv", "_processed.csv"), 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=('start', 'end', 'symbol', 'entry', 'exit', 'size'))
        writer.writeheader()
        for position in positions:
            writer.writerow(position)
