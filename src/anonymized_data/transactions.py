from src.data_connection import get_query
from src.anonymized_data.ranks import Ranks

QUERY = """WITH shifted AS (
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
SELECT rank,logical_day,weekday_number,barcode_prod,COUNT(*) AS amount
	FROM enriched_transactions
	LEFT JOIN users ON users.barcode = enriched_transactions.barcode_user
	GROUP BY rank,logical_day,barcode_prod;
"""
COLUMNS = ["rank","logical_day","weekday_number","barcode_prod","amount"]

class Transactions:
    def __init__(self,ranks:Ranks):
        df = get_query(QUERY,COLUMNS)
        df = df[df['rank'].isin(ranks.included_ranks)]
        self.table = df
