from SimpleWebSocketServer import SimpleWebSocketServer, WebSocket
from enum import Enum, auto
import traceback
import json

# WHY
TEXT = 0x1
BINARY = 0x2

nextLobbyId = 1
nextUserId = 1

class User:
    def __init__(self, client, name):
        global nextUserId
        self.client = client
        self.id = nextUserId
        self.name = name
        self.lobbyID = None
        nextUserId += 1

class Lobby:
    playerCount = 1
    def __init__(self, user: User, name, maxCount):
        global nextLobbyId
        self.ingame = False
        self.name = name
        self.maxCount = maxCount
        self.id = nextLobbyId
        self.host = user
        user.lobbyID = self.id
        self.players = [user]
        nextLobbyId += 1
        self.packets = []

class SimpleChat(WebSocket):
    user = None
    def error(self, reason):
        self.sendMessage(json.dumps({
            "packetID": 255,
            "data": {
                "error": reason
            }
        }))
    def broadcastLobby(self, lobby):
        for client in clients:
            if client.user and client.user.lobbyID == None:
                client.sendMessage(json.dumps({
                    "packetID": 3,
                    "data": {
                        "lobbyID": lobby.id,
                        "lobbyName": lobby.name,
                        "playerCount": len(lobby.players),
                        "maxCount": lobby.maxCount
                    }
                }))
    def sendLobby(self, lobby):
        print(f"D: Sending lobby info to {self.user.name} for lobby {lobby.id}")
        self.sendMessage(json.dumps({
            "packetID": 8,
            "data": {
                "id": lobby.id,
                "ingame": lobby.ingame, 
                "name": lobby.name,
                "maxCount": lobby.maxCount,
                "host": lobby.host.name,
                "players": [player.name for player in lobby.players]
            }
        }))

    def LoginHandler(self, data):
        global users
        if "name" in data and type(data["name"]) == str:
            if data["name"] in users:
                self.user = users[data["name"]]
                self.user.client = self
                self.playback()
            else:
                print("Registering new user")
                self.user = User(self, data["name"])
                users[data["name"]] = self.user
                self.lobbylist()
        else:
            self.error("Give me a name plz")
    def CreateLobbyHandler(self, data):
        if "lobbyName" in data and "maxCount" in data \
            and type(data["lobbyName"]) == str and type(data["maxCount"]) == int:
            lobby = Lobby(self.user, data["lobbyName"], data["maxCount"])
            lobbies[lobby.id] = lobby
            self.broadcastLobby(lobby)
            self.sendLobby(lobby)
        else:
            self.error("Something went wrong in lobby validation")
        return False
    def JoinLobbyHandler(self, data):
        if "lobbyID" in data and type(data["lobbyID"]) == int:
            lobbyID = data["lobbyID"]
            if lobbyID not in lobbies.keys():
                self.error("Unknown lobbyID")
            else:
                lobby = lobbies[lobbyID]
                if len(lobby.players) == lobby.maxCount:
                    self.error("Full lobby")
                    return False
                lobby.players.append(self.user)
                self.user.lobbyID = lobbyID
                # Tell other clients they joined
                for player in lobby.players:
                    print(f"Telling user {player.name} that lobby {lobby.id} changed")
                    player.client.sendLobby(lobby)
                self.broadcastLobby(lobby)
        else:
            self.error("Invalid lobbyID")
    
    def LeaveLobbyHandler(self, data):
        lobby = lobbies[self.user.lobbyID]
        lobbyID = self.user.lobbyID      
        if lobby.host == self.user and lobby.ingame == False:
            # If the host has left the lobby during pregame, tell everyone its dead      
            print(f"Host left the lobby {lobbyID}")
            players = lobby.players
            # Also nuke the lobby itself
            del lobbies[lobbyID]

            for player in players:
                print(f"Kicking user: {player.name}")
                player.lobbyID = None
                player.client.sendMessage(json.dumps({
                    "packetID": 4,
                    "data": {
                        "lobbyID": lobbyID
                    }
                }))
                player.client.lobbylist()
            print(f"D: All users kicked")
            return False
        print(f"{self.user.name} left the lobby {lobbyID}")
        lobby.players.remove(self.user)
        self.user.lobbyID = None
        # Tell other clients they joined
        for player in lobby.players:
            print(f"Telling user {player.name} that lobby {lobby.id} changed")
            player.client.sendLobby(lobby)
        # Trick client into thinking it died
        self.sendMessage(json.dumps({
            "packetID": 4,
            "data": {
                "lobbyID": lobby.id
            }
        }))
        self.lobbylist()
        return False
    def LobbyStartHandler(self, data):
        lobby = lobbies[self.user.lobbyID]
        if len(lobby.players) < 2:
            self.error("Not enough players")
            return False
        if lobby.host != self.user:
            self.error("Not host")
            return False
        lobby.ingame = True
        for player in lobby.players:
            print(f"Telling user {player.name} that lobby {lobby.id} went ingame")
            player.client.sendLobby(lobby)
        return False
    def ChatHandler(self, data):
        if "message" in data and type(data["message"]) == str:
            packet = {
                "packetID": 0,
                "data": {
                    "author": self.user.name,
                    "message": data["message"]
                }
            }
            for client in clients:
                client.sendMessage(json.dumps(packet))
            lobby = lobbies[self.user.lobbyID]

            # Manually appending due to mutating packet server side
            lobby.packets.append(packet)
        else:
            self.error("Invalid message")
        return False
    # Utilized by lambda functions below
    def proxy(self, packetID, data):
        lobby = lobbies[self.user.lobbyID]
        for player in lobby.players:
            player.client.sendMessage(json.dumps({
                "packetID": packetID,
                "data": data
            }))
        return True
    def playback(self):
        if self.user.lobbyID:
            lobby = lobbies[self.user.lobbyID]
            self.sendLobby(lobby)
            for packet in lobby.packets:
                self.sendMessage(json.dumps(packet))
        else:
            self.lobbylist()
    def lobbylist(self):
        result = [{
            "lobbyID": lobby.id,
            "lobbyName": lobby.name,
            "playerCount": len(lobby.players),
            "maxCount": lobby.maxCount
        } for lobby in lobbies.values() if lobby.ingame == False]
        self.sendMessage(json.dumps({
            "packetID": 2,
            "data": {
                "lobbies": result
            }
        }))
    def handleMessage(self):
        try:
            print(self.address, self.data)
            data = {}

            #TODO: Support other encapsulations?
            if self.opcode == TEXT:
                try:
                    data = json.loads(self.data)
                except json.JSONDecodeError as e:
                    print("Ooops", e)
                    return self.error("rip json")
                
            if "packetID" not in data:
                return self.error("No packetID")
            if "data" not in data:
                return self.error("No data object present")
            if not isinstance(data["data"], object):
                return self.error("data isn't an object")
            # packetID and data confirmed to exist
            packetID = data["packetID"]
            payload = data["data"]
            if not self.user:
                if packetID == 1:
                    self.LoginHandler(payload)
                else:
                    self.error("Not logged in")
                return
            # TODO: Cleanup this mess
            if self.user.lobbyID:
                lobby = lobbies[self.user.lobbyID]
                if lobby.ingame:
                    if packetID in self.ingameHandlers.keys():
                        if self.ingameHandlers[packetID](self, payload):
                            lobby.packets.append(data)
                    else:
                        self.error("Unknown ingame packet")
                else:
                    if packetID in self.pregameHandlers.keys():
                        if self.pregameHandlers[packetID](self, payload):
                            lobby.packets.append(data)
                    else:
                        self.error("Unknown pregame packet")
            else:
                if packetID in self.lobbyHandlers.keys():
                    try:
                        self.lobbyHandlers[packetID](self, payload)
                    except:
                        traceback.print_exc()
                else:
                    self.error("Unknown lobby packet")
        except:
            traceback.print_exc()
            self.error(traceback.format_exc)

    def handleConnected(self):
        print(self.address, 'connected')
        try:
            clients.append(self)
        except:
            traceback.print_exc()

    def handleClose(self):
        print(self.address, 'closed')
        clients.remove(self)

        # TODO: Check if in lobby, if so notify lobby members he went poof
        for client in clients:
            pass
            #client.sendMessage(json.dumps({
            #    "packetID": 0,
            #    "data": {
            #        "msg": f"{self.address} has left the fight"
            #    }
            #}))
    lobbyHandlers = {
        6: CreateLobbyHandler,
        7: JoinLobbyHandler
    }
    pregameHandlers = {
        0: ChatHandler,
        5: LeaveLobbyHandler,
        9: LobbyStartHandler
    }
    ingameHandlers = {
        0: ChatHandler,
        10: lambda self,data: self.proxy(10,data) #PlayerRoll
    }

clients = []
users = {}
lobbies = {}

server = SimpleWebSocketServer('0.0.0.0', 8000, SimpleChat)
server.serveforever()