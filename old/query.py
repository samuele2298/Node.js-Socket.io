
def create_tables_query():
    user_table_query = """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100),
            email VARCHAR(100) UNIQUE,
            password VARCHAR(100),
            elo INTEGER
        )
    """

    games_table_query = """
        CREATE TABLE IF NOT EXISTS games (
            id SERIAL PRIMARY KEY,
            game_json JSONB,
            player1_id INTEGER REFERENCES users(id),
            player2_id INTEGER REFERENCES users(id)
        )
    """

    return user_table_query, games_table_query


def insert_user_query(name, email, password):
    return "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)", (name, email, password)

def select_user_by_email_query(email):
    query = "SELECT id, name, email, password FROM users WHERE email = %s"
    params = (email,)
    return query, params
