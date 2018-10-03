from SimpleWebSocketServer import SimpleWebSocketServer, WebSocket
import json

clients = []

# WHY
TEXT = 0x1
BINARY = 0x2

class SimpleChat(WebSocket):

    def handleMessage(self):
        print(self.address, self.data)
        data = {}
        if self.opcode == TEXT:
            try:
                data = json.loads(self.data)
            except json.JSONDecodeError as e:
                print("Ooops", e)
                self.sendMessage(json.dumps({
                    "packetID": 255,
                    "data": {
                        "error": "rip json"
                    }
                }))
                return
            # TODO: Do some sanity checks here
        for client in clients:
            client.sendMessage(json.dumps(data))

    def handleConnected(self):
        clients.append(self)
        print(self.address, 'connected')
        for client in clients:
            client.sendMessage(json.dumps({
                "packetID": 0,
                "data": {
                    "msg": f"{self.address} has joined the fight"
                }
            }))

    def handleClose(self):
        clients.remove(self)
        print(self.address, 'closed')
        for client in clients:
            client.sendMessage(json.dumps({
                "packetID": 0,
                "data": {
                    "msg": f"{self.address} has left the fight"
                }
            }))

server = SimpleWebSocketServer('', 8000, SimpleChat)
server.serveforever()