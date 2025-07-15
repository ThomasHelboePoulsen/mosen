import pandas as pd

from src.data_connection import Database
from src.anonymized_data.ranks import Ranks

COLUMNS = ["rank","logical_day","weekday_name","barcode_prod","amount","distinct_users"]
OUTPUT_COLUMNS = ["rank","logical_day","weekday_name","barcode_prod"]

class Transactions:
    def __init__(self,ranks:Ranks):
        df = Database().get_query(RANK_DAY_ITEM_GROUPED_PURCHASES_QUERY,COLUMNS)
        df = df[df['rank'].isin(ranks.included_ranks)]
        df = self.sanitize_rare_combinations(df)
        self.table = df[OUTPUT_COLUMNS]

    def sanitize_rare_combinations(self,df):
        minimum_unique_users_per_combination = 2
        df['distinct_users'] = pd.to_numeric(df['distinct_users'], errors='coerce')
        unusual_combinations_mask = df['distinct_users'] < minimum_unique_users_per_combination
        df.loc[unusual_combinations_mask, 'barcode_prod'] = 'ANDRE_VARER'
        return df

RANK_DAY_ITEM_GROUPED_PURCHASES_QUERY = """WITH shifted AS (
  SELECT *,
    datetime(
      substr(timestamp, 7, 4) || '-' ||
      substr(timestamp, 4, 2) || '-' ||
      substr(timestamp, 1, 2) || ' ' ||
      substr(timestamp, 12),
    '-5 hours') AS shifted_datetime
  FROM transactions
), enriched_transactions AS
(
	SELECT *,
	  date(shifted_datetime) AS logical_day,
	  strftime('%w', shifted_datetime) AS weekday_number,
	  CASE strftime('%w', shifted_datetime)
		WHEN '0' THEN 'Sunday'
		WHEN '1' THEN 'Monday'
		WHEN '2' THEN 'Tuesday'
		WHEN '3' THEN 'Wednesday'
		WHEN '4' THEN 'Thursday'
		WHEN '5' THEN 'Friday'
		WHEN '6' THEN 'Saturday'
	  END AS weekday_name
	FROM shifted
)
SELECT rank,logical_day,weekday_name,barcode_prod,COUNT(*) AS amount, COUNT(DISTINCT barcode_user) AS distinct_users
	FROM enriched_transactions
	LEFT JOIN users ON users.barcode = enriched_transactions.barcode_user
	GROUP BY rank,logical_day,barcode_prod;
"""
