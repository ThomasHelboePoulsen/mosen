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
        df = get_query(query,columns)
        df["is_included"] = df["is_included"].astype(bool)
        self.table = df
        self.included_ranks = df[df["is_included"]]["ranks"].tolist()
        self.excluded_ranks = df[~df["is_included"]]["ranks"].tolist()
        print(self.table)


