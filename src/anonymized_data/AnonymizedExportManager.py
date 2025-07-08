import zipfile
import io
from src.anonymized_data.ranks import Ranks
from src.anonymized_data.transactions import Transactions


class AnonymizedExportManager():
    def __init__(self):
        self.data = {}
        self.anonymize_data()

    def anonymize_data(self):
        ranks = Ranks()
        self.data["ranks"] = ranks.table
        self.data["transactions"] = Transactions(ranks).table
        pass

    def data_to_zip_buffer(self):
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for table_name,df in self.data.items():
                zf.writestr(f"{table_name}.csv", df.to_csv(index=False))

        zip_buffer.seek(0)
        return zip_buffer
