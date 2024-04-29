// User.js

class Player {
    constructor(sid, name, color) {
        this.sid = sid;
        this.name = name;
        this.color = color;
    }
}


// Room class
class Room {
    constructor(name) {
        this.name = name;
        this.players = []; // Initialize player_map as an empty array
        this.game = null; // Initialize game as null
        this.started = false;
        this.finish = false;
    }

    // Method to add a user to the room
    joinPlayer(player) {
        this.players.push(player);
    }

    // Method to remove a user from the room
    leavePlayer(sid) {
        this.players = this.players.filter(player => player.sid !== sid);
    }

    // Method to start the game
    startGame() {
        this.started = true;
    }

    // Method to finish the game
    finishGame() {
        this.finish = true;
    }

    // Method to modify a player's data
    modifyPlayer(sid, newData) {
        const player = this.players.find(player => player.sid === sid);
        if (player) {
            // Modify the player's data
            Object.assign(player, newData);
        }
        return player;
    }

    // Metodo per ottenere la lista degli utenti
    static getListOfUsers() {
        return this.players;
    }


    // Method to get a player by SID
    getPlayer(sid) {
        return this.players.find(player => player.sid === sid);
    }

    // Method to change the color of a player by name
    changePlayerColor(name, color) {
        const player = this.players.find(player => player.name === name);
        if (player) {
            player.color = color;
        }
    }

    // Method to get room status in the specified format
    getStatus() {
        const players = this.players.map(player => ({
            name: player.name,
            color: player.color
        }));

        return {
            roomName: this.name,
            players: players
        };
    }
}

module.exports = { Player, Room };
