from src.data_connection import Database
import enum

EXCLUDED_STRING = "[EXCLUDED]"

class Ranks:
    def __init__(self,db:Database,aggregation_limit=10):
        self.aggregation_limit = aggregation_limit
        columns = [column.value for column in RanksColumns]
        query = f"""
            SELECT rank AS {RanksColumns.RANKS.value}
                , COUNT(DISTINCT barcode) AS {RanksColumns.USER_COUNT.value},
                COUNT(DISTINCT barcode) >= {aggregation_limit} AS {RanksColumns.IS_INCLUDED.value}
                FROM users
                GROUP BY rank
        """
        df = db.get_query(query,columns)
        df[RanksColumns.IS_INCLUDED.value] = df[RanksColumns.IS_INCLUDED.value].astype(int).astype(bool)
        self.included_ranks = df[df[RanksColumns.IS_INCLUDED.value]][RanksColumns.RANKS.value].tolist()
        self.excluded_ranks = df[~df[RanksColumns.IS_INCLUDED.value]][RanksColumns.RANKS.value].tolist()
        df[RanksColumns.RANKS.value] = df[RanksColumns.RANKS.value].map(lambda x: x if self.included_ranks.count(x) > 0 else EXCLUDED_STRING)
        self.table = df
        print(self.table)


class RanksColumns(enum.Enum):
    RANKS = "ranks"
    USER_COUNT = "user_count"
    IS_INCLUDED = "is_included"


