import json
import time
from flask import Flask, request, jsonify # type: ignore
from flask_socketio import SocketIO, emit  # type: ignore
from model import Game
from flask_cors import CORS # type: ignore
from query import insert_user_query, select_user_by_email_query,create_tables_query
import psycopg2 # type: ignore
from flask_bcrypt import Bcrypt # type: ignore
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity, decode_token
from datetime import datetime, timedelta

# Define the token expiration time (5 minutes)
TOKEN_EXPIRATION_TIME = timedelta(minutes=5)

DATABASE_URL="postgres://ihleullx:0yLbFYH36LAmXc3JHY4lauTo5FoK4tgL@flora.db.elephantsql.com/ihleullx"

app = Flask(__name__)
CORS(app, origins=['http://localhost:*'])
socketio = SocketIO(app, cors_allowed_origins="*" )
bcrypt = Bcrypt(app)
app.config['JWT_SECRET_KEY'] = 'your-secret-key'  # Chiave segreta per firmare i token JWT
jwt = JWTManager(app)

# Dizionario per tenere traccia delle stanze e dei giocatori in ogni stanza
rooms = []
# 'id','name','player_map': {'sid','name','color},'started','finish','game_data'}

logged_users = []
#{'id','email','name','token'}

##############################################################
#FUNCTIONS
import random
import string

def generate_room_id():
    # Genera un ID casuale di 6 caratteri per la stanza
    return ''.join(random.choices(string.ascii_letters + string.digits, k=6))

# Funzione per inviare un oggetto di gioco a tutti i giocatori in una stanza
def send_game_to_room(room_id, player_id, game_data):
    if room_id in rooms:
        for player_id, player_sid in rooms[room_id].items():
            socketio.emit('game_update', {'room_id': room_id, 'player_id': player_id, 'game_data': game_data})


#TOKEN
def generate_token(user_id):
    """
    Genera un token JWT per l'utente specificato.

    Args:
        user_id (str): ID dell'utente per cui generare il token.

    Returns:
        str: Il token JWT generato.
    """
    # Calcola il tempo di scadenza del token
    expiration_time = datetime.utcnow() + TOKEN_EXPIRATION_TIME
    
    # Costruisci il payload del token
    payload = {
        'user_id': user_id,
        'exp': expiration_time
    }
    
    # Genera il token JWT firmando il payload con la chiave segreta
    token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')
    
    return token

def verify_token(token):
    """
    Verifica la validità del token JWT.

    Args:
        token (str): Il token JWT da verificare.

    Returns:
        str or None: Se il token è valido, restituisce l'ID dell'utente estratto dal token. Altrimenti, restituisce None.
    """
    try:
        # Decodifica il token JWT utilizzando la chiave segreta
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        
        # Estrai l'ID dell'utente dal payload
        user_id = payload['user_id']
        
        # Restituisci l'ID dell'utente
        return user_id
    
    except jwt.ExpiredSignatureError:
        # Se il token è scaduto, restituisci None
        return None
    except jwt.InvalidTokenError:
        # Se il token è invalido, restituisci None
        return None

def invalidate_sessions_and_tokens():
    try:
        global logged_users
        
        # Clear the list of logged-in users
        logged_users = []
          
        # Return a success message
        return {'message': 'All sessions and JWT tokens invalidated successfully'}, 200
        
    except Exception as e:
        # Return an error message if an exception occurs
        return {'error': str(e)}, 500

#######################################################
#AUTH

# Funzione per stabilire la connessione al database
def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

# Endpoint per la registrazione di un nuovo utente
@app.route('/registration', methods=['POST'])
def registration():
    data = request.json
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')

    try:
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        query, params = insert_user_query(name, email, hashed_password)
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                connection.commit()
        return jsonify({'message': 'User registered successfully'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Endpoint per il login dell'utente
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    
    print(f"Login email: {email} pass: {password}")

    try:
        query, params = select_user_by_email_query(email)
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                user = cursor.fetchone()
                #crypted_pass = bcrypt.check_password_hash(user['password'], password)
                if user and bcrypt.check_password_hash(user[3], password) and email == user[2]:
                    # Controlla se l'utente ha già un token associato
                    for user_data in logged_users:
                        if user_data['email'] == email:
                            # Se l'utente è già loggato, restituisci un errore
                            return jsonify({'message': 'User already logged in'}), 401
                    
                    # Genera un token JWT per l'utente
                    token = generate_token(email)
                    
                    # Creare un nuovo oggetto user con id e token di accesso
                    user_data = {'id': f'{user[0]}', 'email': user[2], 'name': user[1], 'token': token}
                    
                    # Aggiungere l'utente alla lista degli utenti loggati
                    logged_users.append(user_data)
                    print(f"Aggiunto user: {email}")
        
                    # Restituisci i dati dell'utente e il token JWT
                    return jsonify({'token': token, 'user': user_data}), 200
                else:
                    # Se le credenziali sono invalide, restituisci un errore
                    return jsonify({'message': 'Invalid email or password'}), 401
    except Exception as e:
        # In caso di errore, restituisci un errore generico
        return jsonify({'error': str(e)}), 500
  # Endpoint for logout

@app.route('/logout', methods=['POST'])
def logout():
    try:
        # Estrai il token dalla richiesta HTTP
        token = request.headers.get('Authorization')
        
        # Verifica se il token è presente
        if not token:
            return jsonify({'message': 'Token is missing'}), 401
        
        # Verifica che il token sia nel formato corretto
        token_parts = token.split()
        if len(token_parts) != 2 or token_parts[0].lower() != 'bearer':
            return jsonify({'message': 'Invalid token format'}), 401
        
        # Estrai il token dall'header
        token = token_parts[1]
        
        # Verifica la validità del token
        email = verify_token(token)
        if not email:
            return jsonify({'message': 'Invalid or expired token'}), 401

        # Find the user object in logged_users based on email
        user_to_logout = next((user for user in logged_users if user['email'] == email), None)
        
        if user_to_logout:
            # Invalidate the token by setting its expiration time to a past date
            response = jsonify({'message': 'Logout successful'})
            
            # Rimuovi l'utente dalla lista degli utenti loggati
            logged_users.remove(user_to_logout)
            
            return response, 200
        else:
            return jsonify({'message': 'User not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@app.route('/invalidate_session', methods=['POST'])
def invalidate_sessions_and_tokens_endpoint():
    result, status_code = invalidate_sessions_and_tokens()
    return jsonify(result), status_code

@app.route('/logged_users_count', methods=['GET'])
def get_logged_users_count():
    count = len(logged_users)
    return jsonify({'count': count}), 200

# Endpoint per la creazione delle tabelle
@app.route('/init', methods=['POST'])
def create_tables():
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            user_table_query, games_table_query = create_tables_query()
            cursor.execute(user_table_query)
            cursor.execute(games_table_query)
        connection.commit()
        return jsonify({'message': 'Tables created successfully'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        connection.close()
        
@app.route('/reset_db', methods=['POST'])
def reset_db():
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS users, games")
        connection.commit()
        return jsonify({'message': 'Database reset successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        connection.close()        
  
##############################################################
#SOCKET CONNECTION

@socketio.on('connect')
def handle_connect():
    try: 
        print('Client Connected')  
    except Exception as e:
        print("Errore: ", str(e))

@socketio.on('disconnect')
def handle_disconnect():
    try: 
        print('Client Disonnected')  
    except Exception as e:
        print("Errore: ", str(e))
   

#######################################################
#SOCKET ROOMS

# Endpoint per la creazione di una nuova lobby
@socketio.on('create_room')
def create_room(data):
    try:
        room_name = data['roomName']
        player_name = data['playerName']
        sid= request.sid
        #print("Richiesta ricevuta room: ", room_name)

        # Create a new empty map for the room
        player_map = [{'sid': sid, 'name': player_name, 'color': '1'}] 
        
        game_data = {}

        # Create a new room with the provided parameters
        new_room = {
            'name': room_name,
            'player_map': player_map,
            'started': False,
            'finish': False,
            'game_data': game_data
        }
        
        rooms.append(new_room)   
             
        print("Room created: ", room_name)
    except Exception as e:
        print("Errore: ", str(e))
        
# Endpoint per unirsi a una partita esistente
@socketio.on('join_room')
def player_join_room(data):
    try:
        #print("Request to join room: ", data)
        room_name = data.get('roomName')
        player_name = data.get('playerName')
        sid = request.sid

        if room_name is None or player_name is None:
            print("Error: Both 'roomName' and 'playerName' parameters are required.")
            return

        # Check if the room exists
        if not rooms:
            print("Error: No rooms available.")
            return

        target_room = next((room for room in rooms if room['name'] == room_name), None)
        if target_room is None:
            print(f"Error: Room '{room_name}' not found.")
            return

        # Check if the room has already started the game
        if target_room['started']:
            print("Error: The game has already started.")
            return

        # Add the player to the room
        new_player = {'sid': sid, 'name': player_name, 'color': '1'}
        target_room['player_map'].append(new_player)

        # Emit confirmation message to the client
        for player in target_room['player_map']:
            emit('join_room', {'playerName': player_name, 'color': new_player['color']}, room=player['sid'])

        print("Player joined room: ", player_name)

    except Exception as e:
        print("Error: ", str(e))
        
# Endpoint per lasciare una partita
@socketio.on('leave_room')
def leave_room():
    try: 
        data = request.json
        room_name = data.get('roomName')
        playerName = data.get('playerName')
        
        if room_name is None or playerName is None:
            print("Errore: params is required")

        for room in rooms:
            if room['name'] == room_name:
                for player in room['player_map']:
                    if player['name'] == playerName:
                        room['player_map'].remove(player)                        
                                                
                        socketio.leave(room_name)
                        socketio.broadcast.to(room_name).emit('leave_room', { 'player': player })
                        print("Player leave created: ", player['name'])

                    else:
                        print("Errore: player non trovato")
    
            else:
                print("Errore: Room non trovata")

    except Exception as e:
        print("Errore: ", str(e))

# Endpoint per cambiare il colore nella lobby
@socketio.on('player_change_color')
def player_change_color():
    try:
        data = request.json
        new_color = data.get('color')
        player_name = data.get('player')
        
        for room in rooms:
            for player in room['player_map']:
                if player['name'] == player_name:
                    
                    player['color'] = new_color
                    
                    socketio.broadcast.to(room['name']).emit('player_change_color', {'playerName': player['name'], 'color': new_color})
        
        
       
    except Exception as e:
        print("Errore: ", str(e))


#######################################################
#HTTP ROOM

# Endpoint per ottenere lo stato della stanza
@app.route('/get_room_status', methods=['POST'])
def get_room_status():
    try: 
        # Estrai il token dalla richiesta HTTP
        token = request.headers.get('Authorization')
        
        # Verifica se il token è presente
        if not token:
            return jsonify({'message': 'Token is missing'}), 401
        
        # Verifica che il token sia nel formato corretto
        token_parts = token.split()
        if len(token_parts) != 2 or token_parts[0].lower() != 'bearer':
            return jsonify({'message': 'Invalid token format'}), 401
        
        # Estrai il token dall'header
        token = token_parts[1]
        
        # Verifica la validità del token
        email = verify_token(token)
        if not email:
            return jsonify({'message': 'Invalid or expired token'}), 401

        # Find the user object in logged_users based on email
        user = next((user for user in logged_users if user['email'] == email), None)
        
        if user:
            for room in rooms:
                for player in room['player_map']:
                    if player['name'] == user['name']:
                        return jsonify({'room': room}), 200 
                    else:
                        return jsonify({'message': 'user not in the room'}), 404 
        else:
            return jsonify({'message': 'user not found'}), 404
    except Exception as e:
        return jsonify({'message': str(e)}), 500

# Endpoint per ottenere il roomId dal server in base all'ID del giocatore
@app.route('/get_room_id', methods=['GET'])
def get_room_id():
    try:
        # Estrai il token dalla richiesta HTTP
        token = request.headers.get('Authorization')
        
        # Verifica se il token è presente
        if not token:
            return jsonify({'message': 'Token is missing'}), 401
        
        # Verifica che il token sia nel formato corretto
        token_parts = token.split()
        if len(token_parts) != 2 or token_parts[0].lower() != 'bearer':
            return jsonify({'message': 'Invalid token format'}), 401
        
        # Estrai il token dall'header
        token = token_parts[1]
        
        # Verifica la validità del token
        email = verify_token(token)
        if not email:
            return jsonify({'message': 'Invalid or expired token'}), 401

        # Find the user object in logged_users based on email
        user = next((user for user in logged_users if user['email'] == email), None)
        
        if user:
            # Invalidate the token by setting its expiration time to a past date
            for room in rooms:
                for player in room['player_map']:
                    if player['name'] == user['name']:
                        return jsonify({'roomId': room['id']}), 200  
            
        else:
            return jsonify({'message': 'User not found'}), 404
        
    except Exception as e:
        return jsonify({'message': str(e)}), 500

# Endpoint per ottenere il roomId dal server in base all'ID del giocatore
@app.route('/del_rooms', methods=['GET'])
def del_rooms():

    rooms.clear()  # Cancella tutte le stanze
    return jsonify({'message': 'All rooms deleted'}), 200
    

# Endpoint per ottenere l'elenco dei giochi disponibili
@app.route('/get_list_of_rooms', methods=['GET'])
def get_list_of_rooms():
    try: 
        # Estrai il token dalla richiesta HTTP
        #token = request.headers.get('Authorization')
        
        # Verifica se il token è presente
        #if not token:
        #    return jsonify({'message': 'Token is missing'}), 401
        
        # Verifica che il token sia nel formato corretto
        #token_parts = token.split()
        #if len(token_parts) != 2 or token_parts[0].lower() != 'bearer':
        #    return jsonify({'message': 'Invalid token format'}), 401
        
        # Estrai il token dall'header
        #token = token_parts[1]
        
        # Verifica la validità del token
        #email = verify_token(token)
        #if not email:
        #    return jsonify({'message': 'Invalid or expired token'}), 401

        # Find the user object in logged_users based on email
        #user = next((user for user in logged_users if user['email'] == email), None)
        
        #if user:
        print("Richiesta lista room")
        
        room_status_list = []

        for room in rooms:
            room_name = room['name']
            player_statuses = []

            for player in room['player_map']:
                player_name = player['name']
                color = player['color']
                player_status = {
                    'playerName': player_name,
                    'color': color
                }
                player_statuses.append(player_status)

            room_status = {
                'roomName': room_name,
                'players': player_statuses
            }
            room_status_list.append(room_status)
        #print(room_status_list)
        return json.dumps(room_status_list), 200
        
    except Exception as e:
        print(str(e))
        return jsonify({'message': str(e)}), 500

 
#######################################################
#GAME


# Endpoint per avviare una partita
@app.route('/start_game', methods=['POST'])
def start_game(data):
    room_id = data.get('roomId')
    game_data = data.get('gameData')


    # Verifica se entrambi i dati del gioco e dell'ID della stanza sono presenti nella richiesta
    if game_data and room_id is not None:
        # Esegui la logica per avviare la partita utilizzando i dati del gioco forniti
        # Esempio: Aggiungi il gioco alla stanza corrispondente nell'elenco delle stanze
        # Assicurati di avere un'elenco delle stanze denominato rooms

        # Trova la stanza corrispondente all'ID fornito
        target_room = next((room for room in rooms if room['id'] == room_id), None)

        if target_room and not target_room['started']:
            # Aggiungi il gioco alla stanza corrispondente nell'elenco delle stanze
            target_room['game_data'] = game_data
            # Imposta l'attributo 'started' della stanza su True
            target_room['started'] = True

            # Restituisci una risposta di successo con un messaggio
            return jsonify({'message': 'Partita avviata con successo'}), 200
        else:
            # Se la stanza non è stata trovata, restituisci un errore 404 Not Found
            return jsonify({'error': 'Stanza non trovata'}), 404
    else:
        # Se i dati del gioco o l'ID della stanza non sono forniti nella richiesta, restituisci un errore 400 Bad Request
        return jsonify({'error': 'I dati del gioco o l\'ID della stanza non sono stati forniti'}), 400

# Endpoint per notificare i giocatori nella lobby
@app.route('/update_game', methods=['POST'])
def update_game(data):
    room_id = data.get('roomId')
    game_data = data.get('gameData')

    # Trova la lobby corrispondente all'ID fornito
    target_room = next((room for room in rooms if room['id'] == room_id), None)

    if target_room and target_room['started']:
        target_room['game_data'] = game_data
        
        # Emetti un evento per notificare tutti i giocatori nella lobby
        socketio.emit('update_game', game_data, room=room_id)
        return jsonify({'message': 'Giocatori notificati'}), 200
    else:
        return jsonify({'message': 'Lobby non trovata o partita non ancora avviata'}), 404

# Endpoint per recuperare lo stato del gioco
@app.route('/fetch_game', methods=['GET'])
def fetch_game(data):
    room_id = data.get('roomId')

    # Trova la lobby corrispondente all'ID fornito
    target_room = next((room for room in rooms if room['id'] == room_id), None)

    if target_room:
        game_data = target_room['game_data']
        return jsonify({'game': game_data}), 200
    else:
        return jsonify({'message': 'Lobby non trovata'}), 404

# Endpoint per terminare la partita
@app.route('/end_game', methods=['POST'])
def end_game():
    data = request.json
    room_id = data.get('roomId')

    # Trova la lobby corrispondente all'ID fornito
    target_room = next((room for room in rooms if room['id'] == room_id), None)

    if target_room and target_room['started'] and not target_room['finish']:
        # Esegui la logica per terminare la partita
        # Esempio: Pulisci lo stato della lobby, notifica i giocatori che la partita è finita, ecc.
        # In questo esempio, puliamo semplicemente la stanza
        target_room['started'] = False
        target_room['finish'] = True


        # Assicurati di notificare tutti i giocatori nella lobby che la partita è finita
        socketio.emit('end_game', room=room_id)
        
        return jsonify({'message': 'Partita terminata'}), 200
    else:
        return jsonify({'message': 'Lobby non trovata o partita non ancora avviata'}), 404


#######################################################
#LAUNCH

if __name__ == '__main__':
    socketio.run(app, debug=True, host='127.0.0.1', port=3001)
