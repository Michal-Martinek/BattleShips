import socket, random
from Shared import ConnectionPrimitives


class ConnectedPlayer:
    def __init__(self, id: int):
        self.id: int = id
        self.opponentId: int = 0
        self.inGame: bool = False
    def __repr__(self):
        return f'{self.__class__.__name__}(inGame={self.inGame}, id={self.id}, opponentId={self.opponentId})'
 

class Server:
    def __init__(self, addr):
        self.serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.serverSocket.bind(addr)
        self.serverSocket.listen()

        self.connectedPlayers: dict[int, ConnectedPlayer] = dict()

    def handleQuery(self, conn: socket.socket):
        remoteAddr = conn.getpeername()
        player, command, payload = self._recvQuery(conn)
        
        if command == '!CONNECT':
            print('[INFO] connecting new player', remoteAddr)
            player = self.newConnectedPlayer()
            assert player.id not in self.connectedPlayers
            self.connectedPlayers[player.id] = player
            self._sendResponse(conn, player.id, '!CONNECTED', {'id': player.id})
            return
        assert player is not None, 'incoming id is not in self.connectedPlayers'
        if command == '!CONNECTION_CHECK':
            if player.inGame:
                self._sendResponse(conn, player.id, '!CONNECTION_CHECK_RES')
            else:
                self._sendResponse(conn, player.id, '!OPPONENT_DISCONNECTED')
        elif command == '!PAIR_REQ':
            success = self.pairPlayer(conn, player)
            if success:
                print(f'[INFO] paired {player.id} with {player.opponentId}')           
        elif command == '!DISCONNECT':
            self._sendResponse(conn, player.id, '!DISCONNECT')
            self.disconnectPlayer(player)
        else:
            print(f'[ERROR] {command}: {payload}')
            assert False, 'unreachable'
    
    def disconnectPlayer(self, player):
        poped = self.connectedPlayers.pop(player.id)
        poped.inGame = False
        if poped.opponentId in self.connectedPlayers:
            opponent = self.connectedPlayers[poped.opponentId]
            opponent.inGame = False
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

    def _recvQuery(self, conn: socket.socket) -> tuple[ConnectedPlayer, str, dict]:
        id, command, payload = ConnectionPrimitives.recv(conn)
        player = None
        if id in self.connectedPlayers: 
            player = self.connectedPlayers[id]
        return player, command, payload
    def _sendResponse(self, conn: socket.socket, id: int, command: str, payload: dict={}):
        ConnectionPrimitives.send(conn, id, command, payload)


def serverMain():
    ADDR = (socket.gethostbyname(socket.gethostname()), 1250)
    server = Server(ADDR)
    print(f'server ready and listening at {ADDR[0]}:{ADDR[1]}')
    server.loop()    
if __name__ == '__main__':
    serverMain()
