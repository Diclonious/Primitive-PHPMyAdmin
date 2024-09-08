from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import models
import os

load_dotenv()

from db_common import Base, engine, SessionLocal

DB_URL = os.getenv("DB_URL")
print(f"Database URL: {DB_URL}")
engine = create_engine(DB_URL, echo=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def create_database(name: str):
    # Create a new session
    db = SessionLocal()
    try:

        new_database = models.Database(name=name)


        db.add(new_database)
        db.commit()


        db.refresh(new_database)
        print(f"Database created with ID: {new_database.id}")

    finally:
        db.close()


if __name__ == "__main__":
    create_database("my_new_database")
