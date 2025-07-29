from src.data_connection import Database
from enum import Enum

EXCLUDED_STRING = "[EXCLUDED]"

class Ranks:
    def __init__(self,db:Database,aggregation_limit=10):
        self.aggregation_limit = aggregation_limit
        query = f"""
            SELECT rank AS {Cols.RANKS}
                , COUNT(DISTINCT barcode) AS {Cols.USER_COUNT},
                COUNT(DISTINCT barcode) >= {aggregation_limit} AS {Cols.IS_INCLUDED}
                FROM users
                GROUP BY rank
        """
        df = db.get_query(query,list(Cols))
        self.force_dtypes(df)
        self.included_ranks = df[df[Cols.IS_INCLUDED]][Cols.RANKS].tolist()
        self.excluded_ranks = df[~df[Cols.IS_INCLUDED]][Cols.RANKS].tolist()
        df[Cols.RANKS] = df[Cols.RANKS].map(
            lambda x:
                x if self.included_ranks.count(x) > 0
                else EXCLUDED_STRING
        )
        self.table = df

    def force_dtypes(self,df):
        str_to_bool = [int,bool]
        str_to_int = [int]
        tranformations = {
            Cols.RANKS: [],
            Cols.USER_COUNT: str_to_int,
            Cols.IS_INCLUDED: str_to_bool
        }
        for col, transforms in tranformations.items():
            for transform in transforms:
                df[col] = df[col].astype(transform)


class Cols(str, Enum):
    RANKS       = "ranks"
    USER_COUNT  = "user_count"
    IS_INCLUDED = "is_included"

    def __str__(self):
        return self.value

