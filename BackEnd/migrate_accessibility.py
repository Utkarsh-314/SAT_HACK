from sqlalchemy import inspect, text

from database import engine, User


def migrate():

    table_name = User.__tablename__
    column_name = "disabilities"

    inspector = inspect(engine)

    existing_columns = {
        column["name"]
        for column in inspector.get_columns(table_name)
    }

    if column_name in existing_columns:
        print("Disabilities column already exists.")
        return

    preparer = engine.dialect.identifier_preparer

    quoted_table = preparer.quote(table_name)
    quoted_column = preparer.quote(column_name)

    query = text(
        f"ALTER TABLE {quoted_table} "
        f"ADD COLUMN {quoted_column} JSON NULL"
    )

    with engine.begin() as connection:
        connection.execute(query)

    print("Successfully added disabilities column!")


if __name__ == "__main__":
    migrate()