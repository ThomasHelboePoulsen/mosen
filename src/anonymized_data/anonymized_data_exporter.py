import zipfile
import io
from src.anonymized_data.ranks import Ranks
from src.anonymized_data.transactions import Transactions
from src.data_connection import get_prods
from src.data_connection import Database



class AnonymizedDataExporter():
    def __init__(self):
        self.data = {}
        self.update()

    def update(self):
        db = Database()
        data = {}
        ranks = Ranks(db)
        data["ranks"] = ranks.table
        data["transactions"] = Transactions(db,ranks).table
        data["items"] = db.get_prods()
        self.data = data

    def data_to_zip_buffer(self):
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for table_name,df in self.data.items():
                zf.writestr(f"{table_name}.csv", df.to_csv(index=False))

        zip_buffer.seek(0)
        return zip_buffer
