import psycopg2
import psycopg2.extras # Needed for DictCursor

# --- Database Connection Details ---
# IMPORTANT: Replace these with your actual PostgreSQL credentials
DB_NAME = "bincom_election_db"
DB_USER = "postgres"     # <--- REPLACE THIS with your PostgreSQL username
DB_PASSWORD = "admin" # <--- REPLACE THIS with your PostgreSQL password
DB_HOST = "localhost"
DB_PORT = "5432"

def get_db_connection():
    """Establishes and returns a new database connection."""
    conn = None
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        return conn
    except psycopg2.Error as e:
        print(f"Database connection error: {e}")
        raise # Re-raise the exception for the calling code to handle

def query_db(query, args=(), fetchone=False, fetchall=False, commit=False):
    """
    Executes a database query.

    Args:
        query (str): The SQL query to execute.
        args (tuple): Arguments to pass to the query (for parameterized queries).
        fetchone (bool): If True, fetches only one row.
        fetchall (bool): If True, fetches all rows.
        commit (bool): If True, commits the transaction (for INSERT, UPDATE, DELETE).

    Returns:
        dict or list of dict or None: Query results as dictionaries or None.
    """
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        # Use DictCursor to get results as dictionaries (column_name: value)
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute(query, args)

        if commit:
            conn.commit()
            return None # No data to return for commit operations
        elif fetchone:
            result = cur.fetchone()
            return dict(result) if result else None # Convert Row to dict, handle None
        elif fetchall:
            results = cur.fetchall()
            return [dict(row) for row in results] # Convert all Rows to dicts
        else:
            return None # For queries that don't fetch (e.g., CREATE TABLE, DROP TABLE without RETURNING)

    except psycopg2.Error as e:
        print(f"Database query error: {e}")
        if conn:
            conn.rollback() # Rollback in case of error
        raise # Re-raise the exception after logging/rollback
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

if __name__ == '__main__':
    # This block runs only when database.py is executed directly, not imported
    print("Testing database connection...")
    try:
        conn = get_db_connection()
        if conn:
            print("Successfully connected to the database!")
            conn.close()
        else:
            print("Failed to connect to the database.")
    except Exception as e:
        print(f"Test failed with error: {e}")

    print("\nTesting query_db function for tables...")
    try:
        tables = query_db("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = 'public';", fetchall=True)
        if tables:
            print("Tables in public schema:")
            for table in tables:
                print(f"- {table['tablename']}")
        else:
            print("No tables found or query failed.")
    except Exception as e_query:
        print(f"Query test failed with error: {e_query}")