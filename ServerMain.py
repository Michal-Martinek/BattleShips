import socket, random, time, logging
from typing import Union
from Shared import ConnectionPrimitives
from Shared.CommandNames import *

class ConnectedPlayer:
    def __init__(self, id: int):
        self.connected: bool = True
        self.id: int = id
        self.gameId: int = 0
        self.lastReqTime = time.time()
        self.gameState: dict = {'ready': False}
    @ property
    def inGame(self):
        return self.gameId != 0
    def __repr__(self):
        return f'{self.__class__.__name__}(id={self.id}, gameId={self.gameId}, gameState={self.gameState})'
    def shootingReady(self):
        return self.gameState['ready']
    def disconnect(self):
        self.connected = False

class Game:
    STAGE_PLACING = 1
    STAGE_SHOOTING = 2

    def __init__(self, id, player1: ConnectedPlayer, player2: ConnectedPlayer):
        self.id: int = id
        self.gameActive: bool = True
        self.gameStage: int = Game.STAGE_PLACING
        self.players: dict[int, ConnectedPlayer] = {player1.id: player1, player2.id: player2}
        self.setPlayersForGame()
        self.playerOnTurn: int = 0
        self.shottedPos = [-1, -1]
    def setPlayersForGame(self):
        for p in self.players.values():
            p.gameId = self.id

    def updateGameState(self, player: ConnectedPlayer, state):
        # TODO: validation of the game state?
        assert player.id in self.players, 'trying to update player game state for nonexistent player'
        player.gameState = state
    def getOpponentState(self, player):
        return self.getOpponent(player).gameState

    def getOpponent(self, player: ConnectedPlayer) -> ConnectedPlayer:
        return [p for p in self.players.values() if p.id != player.id][0]
    def swapTurn(self):
        l = list(self.players.keys())
        l.remove(self.playerOnTurn)
        self.playerOnTurn = l[0]
        self.shottedPos = [-1, -1]

    def canBeEnded(self):
        return not (self.gameActive or any([p.connected for p in self.players.values()]))
    def playerDisconnect(self, player: ConnectedPlayer):
        player.disconnect()
        self.gameActive = False
    def canStartShooting(self):
        return self.gameStage == self.STAGE_PLACING and all([p.shootingReady() for p in self.players.values()])
    def startShooting(self):
        assert self.gameStage == self.STAGE_PLACING, 'Game needs to be in the placing stage to be started'
        logging.info(f'starting game id {self.id}')
        self.gameStage = self.STAGE_SHOOTING
        self.playerOnTurn = random.choice(list(self.players.keys()))
    def opponentShotted(self, player: ConnectedPlayer) -> tuple[bool, list[int]]:
        shotted = self.shottedPos != [-1, -1] and player.id != self.playerOnTurn
        pos = self.shottedPos
        if shotted:
            self.swapTurn()
        return shotted, pos
    def shoot(self, player, pos) -> tuple[bool, dict]:
        assert player.id == self.playerOnTurn, 'only player on turn can shoot'
        self.shottedPos = pos
        for ship in self.getOpponentState(player)['ships']:
            x, y = ship['pos']
            horizontal = ship['horizontal']
            size = ship['size']
            if (x <= pos[0] <= x + (size - 1) * horizontal) and (y <= pos[1] <= y + (size - 1) * (not horizontal)):
                hittedSpot = (pos[0] - x) if horizontal else (pos[1] - y)
                ship['hitted'][hittedSpot] = True
                wholeShip = ship if all(ship['hitted']) else None
                return True, wholeShip
        return False, None


class Server:
    MAX_TIME_FOR_DISCONNECT = 15.
    def __init__(self, addr):
        self.serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.serverSocket.bind(addr)
        self.serverSocket.settimeout(1.0)
        self.serverSocket.listen()

        self.players: dict[int, ConnectedPlayer] = dict()
        self.games: dict[int, Game] = dict()

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
    
    def handleQueriesOutGame(self, conn: socket.socket, player: ConnectedPlayer, command: str, payload: dict) -> bool:
        '''handles requests from players who aren't necessary in a game
        @return True if the command was recognized'''
        if command == COM_DISCONNECT:
            self.disconnectPlayer(player)
            self._sendResponse(conn, player.id, COM_DISCONNECT)
        elif command == COM_PAIR:
            game = self.pairPlayer(conn, player)
            if game:
                self.games[game.id] = game
        elif command == COM_CONNECTION_CHECK:
            stayConnected = not player.inGame
            if player.inGame:
                game = self.games[player.gameId]
                stayConnected = game.gameActive
            self._sendResponse(conn, player.id, COM_CONNECTION_CHECK, {'stay_connected': stayConnected})
        else:
            return False
        return True
    
    def handleQueriesInGame(self, conn: socket.socket, player: ConnectedPlayer, command: str, payload: dict, game: Game) -> bool:
        '''handles queries from players who should be in a game
        @return True if the command was recognized'''
        if command == COM_GAME_READINESS:
            approved = False
            if payload['ready'] or game.gameStage == game.STAGE_PLACING:
                game.updateGameState(player, payload)
                approved = True
            self._sendResponse(conn, player.id, COM_GAME_READINESS, {'approved': approved})
        elif command == COM_GAME_WAIT:
            assert player.shootingReady(), 'Don\'t expect a COM_GAME_WAIT from player without being ready'
            if game.canStartShooting():
                game.startShooting()
            # TODO: we should not send the opponents state
            self._sendResponse(conn, player.id, COM_GAME_WAIT, {'started': game.gameStage == game.STAGE_SHOOTING, 'on_turn': game.playerOnTurn, 'opponent_state': game.getOpponentState(player)})
        elif command == COM_SHOOT:
            # NOTE: when the player on turn shoot before the other player makes COM_OPPONENT_SHOT this will crash, because the game.swapOnTurn() didn't yet happen 
            hitted, wholeShip = game.shoot(player, payload['pos'])
            self._sendResponse(conn, player.id, COM_SHOOT, {'hitted': hitted, 'whole_ship': wholeShip})
        elif command == COM_OPPONENT_SHOT:
            shotted, pos = game.opponentShotted(player)
            self._sendResponse(conn, player.id, COM_OPPONENT_SHOT, {'shotted': shotted, 'pos': pos})
        else:
            return False
        return True
    def handleQuery(self, conn: socket.socket):
        player, command, payload = self._recvQuery(conn)
        
        if command == COM_CONNECT:
            logging.info(f'connecting new player from {conn.getpeername()}')
            player = self.newConnectedPlayer()
            assert player.id not in self.players
            self.players[player.id] = player
            self._sendResponse(conn, player.id, COM_CONNECT, {'id': player.id})
            return

        assert isinstance(player, ConnectedPlayer), 'incoming id is not in self.players'
        player.lastReqTime = time.time()

        if self.handleQueriesOutGame(conn, player, command, payload):
            return
        
        assert player.inGame, 'player is expected to be in a game at this point'
        game = self.games[player.gameId]
        
        if not self.handleQueriesInGame(conn, player, command, payload, game):
            assert False, f'unrecognized command: {command}'

    def checkConnections(self):
        for player in self.players.copy().values():
            if time.time() - player.lastReqTime > self.MAX_TIME_FOR_DISCONNECT:
                self.disconnectPlayer(player)
    
    def disconnectPlayer(self, player: ConnectedPlayer):
        logging.info(f'disconnecting player {player.id}')
        if player.inGame:
            game = self.games[player.gameId]
            game.playerDisconnect(player)
            if game.canBeEnded():
                self.endGame(game)
        else:
            self.players.pop(player.id)
    def endGame(self, game: Game):
        logging.info(f'ending game id {game.id}')
        for pid in game.players.keys():
            assert pid in self.players, 'all players in a game should be in connected players'
            self.players.pop(pid)
        self.games.pop(game.id)

    def _pairablePlayers(self, player: ConnectedPlayer):
        return list(filter(lambda p: not p.inGame and p.id != player.id, self.players.values()))
    def pairPlayer(self, conn, player: ConnectedPlayer) -> Union[Game, None]:
        pairable = self._pairablePlayers(player)
        game = None
        if player.inGame:
            assert player.gameId in self.games, 'player with unknown gameId in pairPlayer'
            game = self.games[player.gameId]
        elif len(pairable) > 0:
            opponent = pairable[0]
            game = self.newGame(player, opponent)
            logging.info(f'paired {player.id} with {game.getOpponent(player).id}')

        failed = game is None
        opponentId = 0 if failed else game.getOpponent(player).id
        self._sendResponse(conn, player.id, COM_PAIR, {'paired': not failed, 'opponent_id': opponentId})
        return game

    def newConnectedPlayer(self):
        id = self._generateNewID(self.players)
        return ConnectedPlayer(id)
    def newGame(self, player1, player2):
        id = self._generateNewID(self.games)
        return Game(id, player1, player2)
    def _generateNewID(self, dictOfIds):
        bounds = (1000, 2**20)
        id = random.randint(*bounds)
        while id in dictOfIds:
            id = random.randint(*bounds)
        return id

    def _recvQuery(self, conn: socket.socket) -> tuple[ConnectedPlayer, str, dict]:
        id, command, payload = ConnectionPrimitives.recv(conn)
        player = None
        if id in self.players: 
            player = self.players[id]
        return player, command, payload
    def _sendResponse(self, conn: socket.socket, id: int, command: str, payload: dict={}):
        ConnectionPrimitives.send(conn, id, command, payload)


def serverMain():
    logging.basicConfig(level=logging.INFO)
    ADDR = (socket.gethostbyname(socket.gethostname()), 1250)
    server = Server(ADDR)
    logging.info(f'server ready and listening at {ADDR[0]}:{ADDR[1]}')
    server.loop()    
if __name__ == '__main__':
    serverMain()
