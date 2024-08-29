from pydantic import BaseModel
from typing import List, Optional
from typing import Dict


# Data Validation: They ensure that incoming data (e.g., request bodies) adheres to the required structure and types. This helps catch errors early and prevents invalid data from reaching your application logic.

# Data Serialization: They define how data should be formatted when sending responses back to clients. This ensures consistency in the API responses.

# Pydantic schemas are used to define the structure of data that you send and receive through your API. They help in data validation and serialization. These schemas are not directly tied to the database but rather define how data should look when interacting with your API.
class ColumnCreate(BaseModel):
    name: str
    data_type: str


class RowCreate(BaseModel):
    table_id: int
    values: Dict[str, str]


class Row(BaseModel):
    id: int
    table_id: int
    values: Dict[str, str]  # This should map column names to their corresponding values

    class Config:
        from_attributes = True


class TableCreate(BaseModel):
    name: str
    database_id: int
    columns: List[ColumnCreate]


class Column(BaseModel):
    id: Optional[int]
    name: str
    data_type: str

    class Config:
        from_attributes = True


class Table(BaseModel):
    id: int
    name: str
    database_id: int
    columns: List[Column] = []

    class Config:
        from_attributes = True


class TableWithRows(BaseModel):  # za da pokazhuvam so se row data
    id: int
    name: str
    database_id: int
    columns: List[Column] = []
    rows: List[Row] = []

    class Config:
        from_attributes = True
