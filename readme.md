# Downloading Data
Download stock data

```sh
$ lean data download --dataset "US Equities" --organization "a498f5e0f72498984b9dff7cadd979b3" --data-type "Trade" --ticker "AAPL" --resolution "Daily" --start "20210101" --end "20211231"
```

# Updating A Project
```sh
lean cloud push --project <PROJECT_NAME>
```

# Backtest in the cloud
```sh
lean cloud backtest <PROJECT_NAME> --push
```