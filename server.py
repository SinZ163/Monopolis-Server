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

    def LoginHandler(self, data):
        global users
        if "name" in data and type(data["name"]) == str:
            if data["name"] in users:
                self.user = users[data["name"]]
                self.playback()
            else:
                print("Registering new user")
                self.user = User(self, data["name"])
                users[data["name"]] = self.user
                self.lobbylist()
        else:
            error("Give me a name plz")
    def CreateLobbyHandler(self, data):
        if "name" in data and "maxCount" in data \
            and type(data["name"]) == str and type(data["maxCount"]) == int:
            lobby = Lobby(self.user, data["name"], data["maxCount"])
            lobbies.append(lobby)
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
        else:
            error("Something went wrong in lobby validation")
        return False
    def CloseLobbyHandler(self, data):
        pass
    def JoinLobbyHandler(self, data):
        pass
    def playback(self):
        if self.user.lobbyID:
            lobby = lobbies[self.user.lobbyID]
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
        } for lobby in lobbies if lobby.ingame == False]
        self.sendMessage(json.dumps({
            "packetID": 2,
            "data": {
                "lobbies": result
            }
        }))
            
    #Currently only used for chat
    def proxy(self):
        for client in clients:
            client.sendMessage(json.dumps(data))
        return True
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
                    error("Not logged in")
                return
            # TODO: Cleanup this mess
            if self.user.lobbyID:
                lobby = lobbies[self.user.lobbyID]
                if lobby.ingame:
                    if packetID in self.ingameHandlers.keys():
                        if self.ingameHandlers[packetID](payload):
                            lobby.packets.append(data)
                    else:
                        error("Unknown ingame packet")
                else:
                    if packetID in self.pregameHandlers.keys():
                        if self.pregameHandlers[packetID](payload):
                            lobby.packets.append(data)
                    else:
                        error("Unknown pregame packet")
            else:
                if packetID in self.lobbyHandlers.keys():
                    try:
                        self.lobbyHandlers[packetID](self, payload)
                    except:
                        traceback.print_exc()
                else:
                    error("Unknown lobby packet")
        except:
            traceback.print_exc()
            error(traceback.format_exc)

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
        5: CloseLobbyHandler,
        6: CreateLobbyHandler,
        7: JoinLobbyHandler
    }
    pregameHandlers = {
        0: proxy
    }
    ingameHandlers = {
        # TODO: Populate
    }

clients = []
users = {}
lobbies = []

server = SimpleWebSocketServer('0.0.0.0', 8000, SimpleChat)
server.serveforever()