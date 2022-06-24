import socket, random, time
from Shared import ConnectionPrimitives
from Shared.CommandNames import *


class ConnectedPlayer:
    def __init__(self, id: int):
        self.id: int = id
        self.opponentId: int = 0
        self.inGame: bool = False
        self.lastReqTime = time.time()
        self.shipPlacements: list[dict] = []
    def __repr__(self):
        return f'{self.__class__.__name__}(inGame={self.inGame}, id={self.id}, opponentId={self.opponentId}, boardState={self.boardState})'
 

class Server:
    MAX_TIME_FOR_DISCONNECT = 15.
    def __init__(self, addr):
        self.serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.serverSocket.bind(addr)
        self.serverSocket.settimeout(1.0)
        self.serverSocket.listen()

        self.connectedPlayers: dict[int, ConnectedPlayer] = dict()
    def loop(self):
        while True:
            try:
                conn, addr = self.serverSocket.accept()
            except socket.timeout:
                pass
            else:
                self.handleQuery(conn)
            finally:
                self.checkConnections()

    def handleQuery(self, conn: socket.socket):
        remoteAddr = conn.getpeername()
        player, command, payload = self._recvQuery(conn)
        
        if command == COM_CONNECT:
            print('[INFO] connecting new player', remoteAddr)
            player = self.newConnectedPlayer()
            assert player.id not in self.connectedPlayers
            self.connectedPlayers[player.id] = player
            self._sendResponse(conn, player.id, COM_CONNECT, {'id': player.id})
            return

        assert player is not None, 'incoming id is not in self.connectedPlayers'
        player.lastReqTime = time.time()

        if command == COM_CONNECTION_CHECK:
            self._sendResponse(conn, player.id, COM_CONNECTION_CHECK, {'still_ingame': player.inGame})
        elif command == COM_PAIR:
            success = self.pairPlayer(conn, player)
            if success:
                print(f'[INFO] paired {player.id} with {player.opponentId}')           
        elif command == COM_DISCONNECT:
            self._sendResponse(conn, player.id, COM_DISCONNECT)
            self.disconnectPlayer(player)
        elif command == COM_BOARD_STATE:
            player.shipPlacements = payload['ships']
            # TODO: validation?
            self._sendResponse(conn, player.id, COM_BOARD_STATE)
        else:
            print(f'[ERROR] {command}: {payload}')
            assert False, 'unreachable'

    def checkConnections(self):
        for player in self.connectedPlayers.copy().values():
            if time.time() - player.lastReqTime > self.MAX_TIME_FOR_DISCONNECT:
                print(f'[INFO] disconnecting player {player.id} due to lack of communication')
                self.disconnectPlayer(player)
    
    def disconnectPlayer(self, player):
        poped = self.connectedPlayers.pop(player.id)
        poped.inGame = False
        if poped.opponentId in self.connectedPlayers:
            opponent = self.connectedPlayers[poped.opponentId]
            opponent.inGame = False
    def _pairablePlayers(self, player: ConnectedPlayer):
        return list(filter(lambda p: not p.inGame and p.id != player.id, self.connectedPlayers.values()))
    def pairPlayer(self, conn, player: ConnectedPlayer) -> bool:
        pairable = self._pairablePlayers(player)
        if player.inGame:
            assert player.opponentId != 0, 'player is in game but opponent\'s id is not set'
        elif len(pairable) > 0:
            opponent = pairable[0]
            player.inGame = True
            opponent.inGame = True
            player.opponentId = opponent.id
            opponent.opponentId = player.id
        self._sendResponse(conn, player.id, COM_PAIR, {'paired': player.opponentId != 0, 'opponent_id': player.opponentId})
        return player.opponentId != 0

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
