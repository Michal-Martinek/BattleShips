import socket, random
import sys, os
sys.path.append(os.path.join(os.path.split(sys.path[0])[0], 'Shared'))
import ConnectionPrimitives # type:ignore


class ConnectedPlayer:
    def __init__(self, id):
        self.id = id

class Server:
    def __init__(self, addr):
        self.serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.serverSocket.bind(addr)
        self.serverSocket.listen()

        self.connectedPlayers: dict[int, ConnectedPlayer] = dict()

    def handleQuery(self, conn: socket.socket):
        remoteAddr = conn.getpeername()
        incomingId, command, payload = ConnectionPrimitives.recv(conn)
        print(f'[DEBUG] id {incomingId} command {command}\npayload {payload}')
        
        if command == '!CONNECT':
            print('[INFO] connecting new player', remoteAddr)
            player = self.newConnectedPlayer()
            self.connectedPlayers[player.id] = player
            ConnectionPrimitives.send(conn, incomingId, '!CONNECTED', {'id': player.id}) 
        elif command == '!CONNECTION_CHECK':
            ConnectionPrimitives.send(conn, incomingId, '!CONNECTION_CHECK_RES')
        elif command == '!DISCONNECT':
            ConnectionPrimitives.send(conn, incomingId, '!DISCONNECT')
            exit(1)
        else:
            print(f'[ERROR] {command}: {payload}')
            assert False, 'unreachable'
    
    def loop(self):
        while True:
            conn, addr = self.serverSocket.accept()
            print(f'[INFO] got query from {addr}')
            self.handleQuery(conn)

    def newConnectedPlayer(self):
        id = self.generateNewID()
        return ConnectedPlayer(id)

    def generateNewID(self):
        bounds = (1000, 2**20)
        id = random.randint(*bounds)
        while id in self.connectedPlayers:
            id = random.randint(*bounds)
        return id


def serverMain():
    ADDR = (socket.gethostbyname(socket.gethostname()), 1250)
    server = Server(ADDR)
    print(f'server ready and listening at {ADDR[0]}:{ADDR[1]}')
    server.loop()    
if __name__ == '__main__':
    serverMain()
