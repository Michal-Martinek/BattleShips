import socket, random
import sys, os
sys.path.append(os.path.join(os.path.split(sys.path[0])[0], 'Shared'))
import ConnectionPrimitives # type:ignore


class ConnectedPlayer:
    def __init__(self, id: int):
        self.id: int = id
        self.opponentId: int = 0
        self.inGame: bool = False
 

class Server:
    def __init__(self, addr):
        self.serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.serverSocket.bind(addr)
        self.serverSocket.listen()

        self.connectedPlayers: dict[int, ConnectedPlayer] = dict()

    def handleQuery(self, conn: socket.socket):
        remoteAddr = conn.getpeername()
        incomingId, command, payload = self._recvQuery(conn)
        print(f'[DEBUG] id {incomingId} command {command}\npayload {payload}')
        
        if command == '!CONNECT':
            print('[INFO] connecting new player', remoteAddr)
            player = self.newConnectedPlayer()
            assert player.id not in self.connectedPlayers
            self.connectedPlayers[player.id] = player
            self._sendResponse(conn, incomingId, '!CONNECTED', {'id': player.id}) 
        elif command == '!CONNECTION_CHECK':
            self._sendResponse(conn, incomingId, '!CONNECTION_CHECK_RES')
        elif command == '!PAIR_REQ':
            player = self.connectedPlayers[incomingId]
            success = self.pairPlayer(conn, player)
            if success:
                print(f'[INFO] paired {player.id} with {player.opponentId}')           
        elif command == '!DISCONNECT':
            self._sendResponse(conn, incomingId, '!DISCONNECT')
            exit(1)
        else:
            print(f'[ERROR] {command}: {payload}')
            assert False, 'unreachable'
    def _pairablePlayers(self, player: ConnectedPlayer):
        return list(filter(lambda p: not p.inGame and p.id != player.id, self.connectedPlayers.values()))
    def pairPlayer(self, conn, player: ConnectedPlayer) -> bool:
        if player.inGame:
            assert player.opponentId != 0, 'player is in game but opponent\'s id is not set'
        else:
            pairable = self._pairablePlayers(player)
            if len(pairable) == 0:
                self._sendResponse(conn, player.id, '!UNPAIRED')
                return False
            opponent = pairable[0]
            player.inGame = True
            opponent.inGame = True
            player.opponentId = opponent.id
            opponent.opponentId = player.id
        self._sendResponse(conn, player.id, '!PAIRED', {'opponent_id': player.opponentId})
        return True

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

    def _recvQuery(self, conn: socket.socket) -> tuple[int, str, dict]:
        return ConnectionPrimitives.recv(conn)
    def _sendResponse(self, conn: socket.socket, id: int, command: str, payload: dict={}):
        ConnectionPrimitives.send(conn, id, command, payload)


def serverMain():
    ADDR = (socket.gethostbyname(socket.gethostname()), 1250)
    server = Server(ADDR)
    print(f'server ready and listening at {ADDR[0]}:{ADDR[1]}')
    server.loop()    
if __name__ == '__main__':
    serverMain()
