import time
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from .config import AUTH_METHOD, DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER


def get_connection_string():
    driver = "ODBC+Driver+17+for+SQL+Server"
    host = f"{DB_HOST}:{DB_PORT}" if DB_PORT else DB_HOST

    if AUTH_METHOD.name == "WINDOWS_AUTH":
        return (
            f"mssql+pyodbc://@{host}/{DB_NAME}?driver={driver}&trusted_connection=yes"
        )
    else:  # SQL_SERVER_AUTH
        return (
            f"mssql+pyodbc://{DB_USER}:{DB_PASSWORD}@{host}/{DB_NAME}?driver={driver}"
        )


connection_string = get_connection_string()
print(f"Using connection string: {connection_string}")  # Debugging output
engine = create_engine(connection_string, echo=False, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


def commit_with_retry(
    session: Session,
    max_retries: int = 4,
    initial_delay: float = 0.5,
    backoff_factor: float = 2.0,
) -> None:
    """
    Commit a SQLAlchemy session with exponential backoff for transient failures.
    """
    initial_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    delay = initial_delay
    for attempt in range(1, max_retries + 1):
        try:
            session.commit()
            if attempt > 1:
                success_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(
                    f"\n[{success_timestamp}] Commit succeeded on attempt {attempt}/{max_retries}",
                    flush=True,
                )
            return
        except Exception as exception:
            session.rollback()
            attempt_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if attempt == 1:
                print(
                    f"\n[{initial_timestamp}] Initial commit attempt failed: {exception}",
                    flush=True,
                )
            else:
                print(
                    f"\n[{attempt_timestamp}] Commit retry {attempt}/{max_retries} failed: {exception}",
                    flush=True,
                )
            if attempt >= max_retries:
                raise
            retry_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(
                f"\n[{retry_timestamp}] Retrying commit in {delay:.1f} seconds",
                flush=True,
            )
            time.sleep(delay)
            delay *= backoff_factor


# Quick DB connectivity test

if __name__ == "__main__":
    print("Testing database connectivity...")
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("Database connection successful.")
    except Exception as e:
        print("Database connection test failed:", e)
        import traceback

        traceback.print_exc()
        raise SystemExit(1) from None
