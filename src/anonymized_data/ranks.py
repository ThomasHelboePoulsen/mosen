import pandas as pd
from src.data_connection import get_query

class Ranks:
    def __init__(self,aggregation_limit=10):
        columns = ["ranks","user_count","is_included"]
        query = f"""
            SELECT rank AS {columns[0]}
                , COUNT(DISTINCT barcode) AS {columns[1]},
                COUNT(DISTINCT barcode) >= {aggregation_limit} AS {columns[2]}
                FROM users
                GROUP BY rank
        """
        self.table = get_query(query,columns)
        print(self.table)


