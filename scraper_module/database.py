from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from .config import DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, AUTH_METHOD

def get_connection_string():
    driver = "ODBC+Driver+17+for+SQL+Server"
    if AUTH_METHOD.name == "WINDOWS_AUTH":
        return (
            f"mssql+pyodbc://@{DB_HOST}/{DB_NAME}"
            f"?driver={driver}&trusted_connection=yes"
        )
    else:  # SQL_SERVER_AUTH
        return (
            f"mssql+pyodbc://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
            f"?driver={driver}"
        )

connection_string = get_connection_string()
print(f"Using connection string: {connection_string}")  # Debugging output
engine = create_engine(connection_string, echo=False)
SessionLocal = sessionmaker(bind=engine)


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
        raise SystemExit(1)