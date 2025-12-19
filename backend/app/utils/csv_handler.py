import pandas as pd
from io import StringIO, BytesIO
from fastapi import UploadFile

def read_csv_file(file: UploadFile) -> pd.DataFrame:
    """Read UploadFile as Pandas DataFrame"""
    content = file.file.read()
    s = str(content, 'utf-8')
    data = StringIO(s)
    df = pd.read_csv(data)
    return df

def df_to_csv_bytes(df: pd.DataFrame) -> BytesIO:
    """Convert DataFrame back to CSV Bytes for download"""
    output = BytesIO()
    df.to_csv(output, index=False, encoding='utf-8-sig') # utf-8-sig for Excel compatibility
    output.seek(0)
    return output
