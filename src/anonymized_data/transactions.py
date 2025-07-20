import pandas as pd
from enum import Enum
from src.data_connection import Database
from src.anonymized_data.ranks import Ranks

PRODUCT_SANITIEZED_STR = "ANDRE_VARER"

class Transactions:
    def __init__(self,db:Database,ranks:Ranks):
        df = db.get_query(RANK_DAY_ITEM_GROUPED_PURCHASES_QUERY,list(Cols))
        self.force_dtypes(df)
        df = df[df[Cols.RANK].isin(ranks.included_ranks) | df[Cols.RANK].isna()]
        df = self.sanitize_rare_combinations(df)
        output_columns = [Cols.RANK, Cols.LOGICAL_DAY, Cols.WEEKDAY_NAME, Cols.BARCODE_PROD,Cols.AMOUNT]
        self.table = df[output_columns]

    def sanitize_rare_combinations(self,df):
        minimum_unique_users_per_combination = 2
        df['distinct_users'] = pd.to_numeric(df['distinct_users'], errors='coerce')
        unusual_combinations_mask = df['distinct_users'] < minimum_unique_users_per_combination
        df.loc[unusual_combinations_mask, 'barcode_prod'] = PRODUCT_SANITIEZED_STR
        return df


    def force_dtypes(self,df):
        str_to_int = [int]
        tranformations = {
            Cols.AMOUNT: str_to_int,
            Cols.DISTINCT_USERS: str_to_int
        }
        for col, transforms in tranformations.items():
            for transform in transforms:
                df[col] = df[col].astype(transform)

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


class Cols(str, Enum):
    RANK            = "rank"
    LOGICAL_DAY     = "logical_day"
    WEEKDAY_NAME    = "weekday_name"
    BARCODE_PROD    = "barcode_prod"
    AMOUNT          = "amount"
    DISTINCT_USERS  = "distinct_users"

    def __str__(self):
        return self.value
