const express = require('express');
const http = require('http');
const socketio = require('socket.io');
const bcrypt = require('bcrypt');
const jwt = require('jsonwebtoken');
const { Pool } = require('pg');
const cors = require('cors');
const { Player, Room } = require('./model');

const app = express();
const PORT = 3001;
const DATABASE_URL = "postgres://ihleullx:0yLbFYH36LAmXc3JHY4lauTo5FoK4tgL@flora.db.elephantsql.com/ihleullx"
const TOKEN_EXPIRATION_TIME = 3600; // Token expiration time in seconds (1 hour)
const JWT_SECRET = 'your_secret_key_here';

app.use(cors());
app.use(express.json());

const server = http.createServer(app);
const io = socketio(server, {
    transports: ['websocket']
});

const pool = new Pool({
    connectionString: DATABASE_URL,
    ssl: {
        rejectUnauthorized: false
    }
});


///////////////////////////////////////////////
//STRUCTURE AND CONST

// Array per tenere traccia delle stanze e dei giocatori in ogni stanza
const rooms = [];

// Array per tenere traccia degli utenti loggati
logged_users = [];

///////////////////////////////////////////////
//METODI


// TOKEN

function generateToken(email) {
    // Calculate token expiration time
    const expirationTime = Math.floor(Date.now() / 1000) + TOKEN_EXPIRATION_TIME;

    // Construct the token payload
    const payload = {
        email: email,
        exp: expirationTime
    };

    // Generate the JWT token by signing the payload with the secret key
    const token = jwt.sign(payload, JWT_SECRET, { algorithm: 'HS256' });

    return token;
}

function verifyToken(token) {
    try {
        // Decode the JWT token using the secret key
        const decoded = jwt.verify(token, SECRET_KEY);

        // Extract the user ID from the payload
        const email = decoded.email;

        // Return the user ID
        return email;
    } catch (error) {
        // If token is expired or invalid, return null
        return null;
    }
}


///////////////////////////////////////////////
//SOCKET ROOM

io.on('connection', (socket) => {
    console.log('Client connected:', socket.id);

    // Gestione della creazione di una nuova stanza
    socket.on('create_room', (data, ack) => {
        try {
            const { roomName, playerName } = data;
            const sid = socket.id;

            if (!roomName || !playerName) {
                console.error('Error: Both "roomName" and "playerName" parameters are required.');
                ack({ error: 'Error: Both "roomName" and "playerName" parameters are required.' });
                return;
            }

            const room = new Room(roomName);
            const player = new Player(sid, playerName, '1');
            room.joinPlayer(player);
            rooms.push(room);

            socket.join(roomName);
            socket.emit('room_created', room)

            ack(room.getStatus())

            console.log('Room created:', room.getStatus());

        } catch (error) {
            console.error('Error:', error);
            socket.emit('error', error.toString());
            ack({ error: error.message });
        }
    });

    // Gestione della richiesta di unirsi a una stanza esistente
    socket.on('join_room', (data, ack) => {
        try {
            const { roomName, playerName } = data;
            const sid = socket.id;

            if (!roomName || !playerName) {
                console.error('Error: Both "roomName" and "playerName" parameters are required.');
                ack({ error: 'Error: Both "roomName" and "playerName" parameters are required.' });
                return;
            }

            else if (!rooms.length) {
                console.error('Error: No rooms available.');
                ack({ error: 'Error: No rooms available.' });
                return;
            }

            const room = rooms.find(room => room.name === roomName);
            if (!room) {
                console.error(`Error: Room '${roomName}' not found.`);
                ack({ error: `Error: Room '${roomName}' not found.` });
                return;
            }

            if (room.started) {
                console.error('Error: The game has already started.');
                ack({ error: 'Error: The game has already started.' });
                return;
            }

            // Aggiungi il giocatore alla stanza
            const newPlayer = new Player(sid, playerName, "1");
            room.joinPlayer(newPlayer);

            socket.join(roomName);
            socket.to(roomName).emit('player_joined', room.getStatus());

            ack(room.getStatus());

            console.log('Player joined room:', playerName);

        } catch (error) {
            console.error('Error:', error);
            socket.emit('error', error.toString());
            ack({ error: error.message });
        }
    });

    // Gestione della richiesta di lasciare una stanza
    socket.on('leave_room', (data, ack) => {
        try {

            // Find the room where the player is located based on their session ID (socket.id)
            const room = rooms.find(room => room.getPlayer(socket.id));

            if (room) {
                const player = room.getPlayer(socket.id)
                // Remove the player from the room
                room.leavePlayer(socket.id);
                // Leave the socket.io room
                socket.leave(roomName);
                // Emit an event to inform other clients that the player has left
                socket.to(roomName).emit('player_leaved', room.getStatus());
                // Send an acknowledgment to the client
                ack(room.getStatus());
                // Log that the player has left the room
                console.log('Player left room:', player.name);
            } else {
                console.error('Error: Player not found in the room.');
                ack({ error: 'Error: Player not found in the room.' });
            }

        } catch (error) {
            console.error('Error:', error);
            socket.emit('error', error.toString()); // Emit 'error' event with the error message
            ack({ error: error.message });

        }
    });

    // Gestione della richiesta di lasciare una stanza
    socket.on('del_room', (data, ack) => {
        try {

            if (rooms.length === 0) {
                console.error('Error: No room present');
                return ack({ error: 'Error: No room present' });
            }

            const room = rooms.find(room => room.getPlayer(socket.id));
            if (room) {
                room.leavePlayer(socket.id);
                // Leave the socket.io room
                socket.leave(room.name);
                // Emit an event to inform other clients that the player has left
                socket.to(room.name).emit('player_leaved', room.getStatus());

                const roomIndex = rooms.findIndex(room => room.id === room.id);

                if (roomIndex !== -1) {
                    rooms.splice(roomIndex, 1);
                    socket.broadcast.emit('room_deleted', room.getStatus());
                    console.error('Room deleted: ', room.name);


                } else {
                    console.error('Error: Room not found.');
                    ack({ error: 'Error: Room not found.' });
                }

                // Ottenere l'elenco delle stanze disponibili
                const roomsStatus = rooms.map(room => room.getStatus());

                const roomsStatusString = JSON.stringify(roomsStatus);

                ack(roomsStatusString);

            } else {
                console.error('Error: Player not found in the room.');
                ack({ error: 'Error: Player not found in the room.' });
            }

        } catch (error) {
            console.error('Error:', error);
            socket.emit('error', error.toString()); // Emit 'error' event with the error message
            return ack({ error: error.message });

        }
    });


    // Gestione del cambio di colore da parte del giocatore nella lobby
    socket.on('change_color', (data, ack) => {
        try {
            const { color } = data;

            if (!color) {
                console.error('Error: Both "color" and "playerName" parameters are required.');
                ack({ error: 'Error: Both "color" and "playerName" parameters are required.' });

                return;
            }

            if (!rooms.length) {
                console.error('Error: No rooms available.');
                ack({ error: 'Error: No rooms available.' });
                return;
            }


            // Find the room where the player is located based on their session ID (socket.id)
            const room = rooms.find(room => room.getPlayer(socket.id));
            if (!room) {
                console.error('Error: Player is not in any room.');
                ack({ error: 'Error: Player is not in any room.' });

                return;
            }

            // Find the player in the room based on their name (playerName)
            const player = room.players.find(player => player.name === playerName);
            if (!player) {
                console.error('Error: Player not found in the room.');
                ack({ error: 'Error: Player not found in the room.' });

                return;
            }

            // Update the player's color to the new color provided
            player.color = color;
            const playerName = player.name;


            // Optionally, emit an event to inform other clients about the color change
            socket.to(room.name).emit('player_change_color', room.getStatus());

            // Send an acknowledgment to the client
            ack(room.getStatus());

            console.log(`Player '${playerName}' changed color to '${color}' in room '${room.name}'.`);

        } catch (error) {
            console.error('Error:', error);
            socket.emit('error', error.toString());
            ack({ error: error.message });
        }
    });

    // Ascolto dell'evento 'get_rooms' dal client
    socket.on('get_rooms', (data, ack) => {
        try {
            // Ottenere l'elenco delle stanze disponibili
            const roomsStatus = rooms.map(room => room.getStatus());
            if (rooms.length === 0) {
                ack({ error: 'Error: No room present' });
            }
            const roomsStatusString = JSON.stringify(roomsStatus);

            ack(roomsStatusString);

        } catch (error) {
            console.error('Error:', error);
            //socket.emit('error', error.toString());

            ack({ error: error.message });
        }
    });

    // Ascolto dell'evento 'get_rooms' dal client
    socket.on('get_room', (data, ack) => {
        try {
            // Find the player in the room based on their name (playerName)
            const room = rooms.find(room => room.getPlayer(socket.id));
            if (!room) {
                console.error('Error: Player is not in any room.');
                ack({ error: 'Error: Player is not in any room.' });
                return;
            }

            ack(room.getStatus());

        } catch (error) {
            ack({ error: error.message });
        }
    });


    //DISCONNECTs
    socket.on('disconnect', () => {
        console.log(`Player disconnected: ${socket.id}`);
    });

    socket.on('reconnect', () => {
        console.log(`Player reconnected: ${socket.id}`);
    });

});



///////////////////////////////////////////////
//HTTP

// Endpoint per la registrazione di un nuovo utente
app.post('/registration', async (req, res) => {
    const { name, email, password } = req.body;

    try {
        const hashedPassword = await bcrypt.hash(password, 10);
        const query = 'INSERT INTO users (name, email, password) VALUES ($1, $2, $3)';
        await pool.query(query, [name, email, hashedPassword]);
        res.status(201).json({ message: 'User registered successfully' });
    } catch (error) {
        console.error(error);
        res.status(500).json({ error: 'Internal server error' });
    }
});

// Endpoint per il login dell'utente
app.post('/login', async (req, res) => {
    const { email, password } = req.body;

    try {
        const query = 'SELECT * FROM users WHERE email = $1';
        const result = await pool.query(query, [email]);
        const user = result.rows[0];

        if (user && await bcrypt.compare(password, user.password) && email === user.email) {
            // Genera un token JWT per l'utente
            const token = generateToken(email)

            // Create a new user object with id and access token
            const user_data = { id: `${user[0]}`, email: user[2], name: user[1], token: token };

            // Add the user to the list of logged-in users
            logged_users.push(user_data);
            console.log(`Added user: ${email}`);

            // Restituisci i dati dell'utente e il token JWT
            res.status(200).json({ token, user });
        } else {
            // Se le credenziali sono invalide, restituisci un errore
            res.status(401).json({ message: 'Invalid email or password' });
        }
    } catch (error) {
        console.error(error);
        res.status(500).json({ error: 'Internal server error' });
    }
});

// Endpoint per il logout
app.post('/logout', async (req, res) => {
    try {
        // Estrai il token dalla richiesta HTTP
        const token = req.headers.authorization;

        // Verifica se il token è presente
        if (!token) {
            return res.status(401).json({ message: 'Token is missing' });
        }

        // Verifica che il token sia nel formato corretto
        const tokenParts = token.split(' ');
        if (tokenParts.length !== 2 || tokenParts[0].toLowerCase() !== 'bearer') {
            return res.status(401).json({ message: 'Invalid token format' });
        }

        // Estrai il token dall'header
        const accessToken = tokenParts[1];

        // Verifica la validità del token
        const email = verifyToken(accessToken);

        // Find the user object in logged_users based on email
        const user_to_logout = logged_users.find(user => user.email == email);

        if (user_to_logout) {

            // Remove the user from the list of logged-in users
            const index = logged_users.indexOf(user_to_logout);
            if (index !== -1) {
                logged_users.splice(index, 1);
            }


            // Invalidate the token by setting its expiration time to a past date
            return res.status(200).json({ message: 'Logout successful' });

        }


    } catch (error) {
        console.error(error);
        return res.status(500).json({ error: 'Internal server error' });
    }
});

// Endpoint per invalidare sessioni e token
app.post('/invalidate_session', (req, res) => {
    try {
        // Pulisci la lista degli utenti loggati
        loggedUsers = [];
        // Restituisci un messaggio di successo
        return res.status(200).json({ message: 'All sessions and JWT tokens invalidated successfully' });
    } catch (error) {
        console.error(error);
        // Restituisci un messaggio di errore se si verifica un'eccezione
        return res.status(500).json({ error: 'Internal server error' });
    }
});

// Endpoint per ottenere il conteggio degli utenti loggati
app.get('/logged_users_count', (req, res) => {
    try {
        // Implementa la logica per ottenere il conteggio degli utenti loggati
        const count = logged_users.length;
        return res.status(200).json({ count });
    } catch (error) {
        console.error(error);
        return res.status(500).json({ error: 'Internal server error' });
    }
});

// Endpoint per la creazione delle tabelle nel database
app.post('/init', async (req, res) => {
    try {
        const connection = await pool.connect();
        const createTablesQuery = `
      CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        email VARCHAR(255) NOT NULL UNIQUE,
        password VARCHAR(255) NOT NULL
      );
      CREATE TABLE IF NOT EXISTS games (
        id SERIAL PRIMARY KEY,
        -- Definire la struttura della tabella dei giochi
      );
    `;
        await connection.query(createTablesQuery);
        connection.release();
        return res.status(201).json({ message: 'Tables created successfully' });
    } catch (error) {
        console.error(error);
        return res.status(500).json({ error: 'Internal server error' });
    }
});

// Endpoint per resettare il database
app.post('/reset_db', async (req, res) => {
    try {
        const connection = await pool.connect();
        await connection.query('DROP TABLE IF EXISTS users, games');
        connection.release();
        return res.status(200).json({ message: 'Database reset successfully' });
    } catch (error) {
        console.error(error);
        return res.status(500).json({ error: 'Internal server error' });
    }
});


///////////////////////////////////////////////
//HTTP ROOM

// Endpoint per ottenere lo stato della stanza
app.post('/get_room_status', (req, res) => {
    try {
        const token = req.headers.authorization;
        if (!token) {
            return res.status(401).json({ message: 'Token is missing' });
        }
        const email = verifyToken(token.split(' ')[1]);
        if (!email) {
            return res.status(401).json({ message: 'Invalid or expired token' });
        }

        const user = logged_users.find(user => user.email === email);
        if (!user) {
            return res.status(404).json({ message: 'User not found' });
        }

        for (const room of rooms) {
            for (const player of room.player_map) {
                if (player.name === user.name) {
                    return res.status(200).json({ room: room });
                }
            }
        }

        return res.status(404).json({ message: 'User not in the room' });
    } catch (error) {
        return res.status(500).json({ message: error.message });
    }
});

// Endpoint per ottenere il roomId dal server in base all'ID del giocatore
app.get('/get_room_id', (req, res) => {
    try {
        const token = req.headers.authorization;
        if (!token) {
            return res.status(401).json({ message: 'Token is missing' });
        }
        const email = verifyToken(token.split(' ')[1]);
        if (!email) {
            return res.status(401).json({ message: 'Invalid or expired token' });
        }

        const user = logged_users.find(user => user.email === email);
        if (!user) {
            return res.status(404).json({ message: 'User not found' });
        }

        for (const room of rooms) {
            for (const player of room.player_map) {
                if (player.name === user.name) {
                    return res.status(200).json({ roomId: room.id });
                }
            }
        }

        return res.status(404).json({ message: 'User not in any room' });
    } catch (error) {
        return res.status(500).json({ message: error.message });
    }
});

// Endpoint per cancellare tutte le stanze
app.get('/del_rooms', (req, res) => {
    try {
        rooms = [];
        return res.status(200).json({ message: 'All rooms deleted' });
    } catch (error) {
        return res.status(500).json({ message: error.message });
    }
});

// Endpoint per ottenere l'elenco delle stanze disponibili
app.get('/get_list_of_rooms', (req, res) => {
    try {
        const roomStatusList = rooms.map(room => {
            const playerStatuses = room.player_map.map(player => ({
                name: player.name,
                color: player.color
            }));
            return {
                roomName: room.name,
                players: playerStatuses
            };
        });
        return res.status(200).json(roomStatusList);
    } catch (error) {
        return res.status(500).json({ message: error.message });
    }
});


// Avvio del server
server.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
});