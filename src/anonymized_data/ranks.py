from src.data_connection import Database

class Ranks:
    def __init__(self,db:Database,aggregation_limit=10):
        columns = ["ranks","user_count","is_included"]
        query = f"""
            SELECT rank AS {columns[0]}
                , COUNT(DISTINCT barcode) AS {columns[1]},
                COUNT(DISTINCT barcode) >= {aggregation_limit} AS {columns[2]}
                FROM users
                GROUP BY rank
        """
        df = db.get_query(query,columns)
        df["is_included"] = df["is_included"].astype(int).astype(bool)
        self.table = df
        self.included_ranks = df[df["is_included"]]["ranks"].tolist()
        self.excluded_ranks = df[~df["is_included"]]["ranks"].tolist()
        print(self.table)


