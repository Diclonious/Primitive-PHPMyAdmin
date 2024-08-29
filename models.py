from sqlalchemy import Column as SaColumn, Integer, String as SaString, ForeignKey, Enum as SaEnum, Boolean, JSON
from sqlalchemy.orm import relationship
from db_common import Base
from enum import Enum


class ColumnDataType(Enum):
    INTEGER = "INTEGER"
    VARCHAR = "VARCHAR"
    TEXT = "TEXT"
    BOOLEAN = "BOOLEAN"
    DATE = "DATE"
    FLOAT = "FLOAT"


class Database(Base):
    __tablename__ = "databases"

    id = SaColumn(Integer, primary_key=True, index=True,autoincrement=True)
    name = SaColumn(SaString(255), unique=True, index=True)

    tables = relationship("Table", back_populates="database")


class Table(Base):
    __tablename__ = "tables"

    id = SaColumn(Integer, primary_key=True, index=True,autoincrement=True)
    name = SaColumn(SaString(255), index=True)
    database_id = SaColumn(Integer, ForeignKey("databases.id"))

    database = relationship("Database", back_populates="tables")
    columns = relationship("TableColumn", back_populates="table")
    rows = relationship("Row", back_populates="table")


class TableColumn(Base):  # Renamed from Column to TableColumn
    __tablename__ = "columns"

    id = SaColumn(Integer, primary_key=True, index=True,autoincrement=True)
    name = SaColumn(SaString(255), index=True)
    data_type = SaColumn(SaEnum(ColumnDataType, name="column_data_type"))
    table_id = SaColumn(Integer, ForeignKey("tables.id"))

    table = relationship("Table", back_populates="columns")
    values = relationship("Value", back_populates="column")

    is_primary_key = SaColumn(Boolean, default=False)


class Row(Base):
    __tablename__ = "rows"

    id = SaColumn(Integer, primary_key=True, index=True,autoincrement=True)
    table_id = SaColumn(Integer, ForeignKey("tables.id"))
    data = SaColumn(JSON)

    table = relationship("Table", back_populates="rows")
    values = relationship("Value", back_populates="row")


class Value(Base):
    __tablename__ = "values"

    id = SaColumn(Integer, primary_key=True, index=True,autoincrement=True)
    row_id = SaColumn(Integer, ForeignKey("rows.id"))
    column_name = SaColumn(SaString(255), index=True)
    column_id = SaColumn(Integer, ForeignKey("columns.id"))
    value = SaColumn(SaString(255))

    row = relationship("Row", back_populates="values")
    column = relationship("TableColumn", back_populates="values")
