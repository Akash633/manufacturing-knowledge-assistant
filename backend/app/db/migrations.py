from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def ensure_review_origin_column(engine: Engine) -> None:
    inspector = inspect(engine)
    if not inspector.has_table("review_items"):
        return

    columns = {column["name"] for column in inspector.get_columns("review_items")}
    if "origin" in columns:
        return

    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE review_items ADD COLUMN origin VARCHAR(24)")
        )
