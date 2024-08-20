from pydantic import BaseModel
from typing import List


class ColumnCreate(BaseModel):
    name: str
    data_type: str


class TableCreate(BaseModel):
    name: str
    database_id: int
    columns: List[ColumnCreate]


class Column(BaseModel):
    id: int
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
