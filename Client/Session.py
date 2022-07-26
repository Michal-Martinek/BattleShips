import socket, time
from Shared import ConnectionPrimitives
from Shared.Enums import COM

class Session:
    SERVER_ADDRES = ('192.168.0.159', 1250)
    TIME_BETWEEN_REQUESTS = 1.0
    
    def __init__(self):
        self.id: int = 0
        self.inGame: bool = False
        self.opponentId: int = 0
        self.timers: dict[str, float] = {}
        self.resetAllTimers()
        
        self._connect()
    def resetTimer(self, timer: str):
        self.timers[timer] = 0.0
    def resetAllTimers(self):
        self.timers = {COM.CONNECTION_CHECK: 0.0, COM.PAIR: 0.0, COM.GAME_WAIT: 0.0, COM.OPPONENT_SHOT: 0.0}
    def close(self):
        self._makeReq(COM.DISCONNECT)
    # TODO: maybe it would be useful to have a function which would make a request periodically after some time
    def ensureConnection(self) -> bool:
        if self.timers[COM.CONNECTION_CHECK] < time.time()-self.TIME_BETWEEN_REQUESTS:
            payload = self._makeReq(COM.CONNECTION_CHECK, updateTimer=COM.CONNECTION_CHECK)
            return payload['stay_connected']
        return True
    def lookForOpponent(self) -> bool:
        if self.timers[COM.PAIR] < time.time()-self.TIME_BETWEEN_REQUESTS:
            res = self._makeReq(COM.PAIR, updateTimer=COM.PAIR)
            if res['paired']:
                self.inGame = True
                self.opponentId = res['opponent_id']
            return res['paired']
    def sendReadyForGame(self, state: dict):
        ret = self._makeReq(COM.GAME_READINESS, state)
        return ret['approved']
    def waitForGame(self) -> tuple[bool, bool]:
        if self.timers[COM.GAME_WAIT] < time.time()-self.TIME_BETWEEN_REQUESTS:
            res = self._makeReq(COM.GAME_WAIT, updateTimer=COM.GAME_WAIT)
            if res['started']:
                return True, res['on_turn'] == self.id
        return False, False
    def opponentShot(self) -> tuple[tuple[int, int], bool]:
        if self.timers[COM.OPPONENT_SHOT] < time.time()-self.TIME_BETWEEN_REQUESTS:
            res = self._makeReq(COM.OPPONENT_SHOT, updateTimer=COM.OPPONENT_SHOT)
            if res['shotted']:
                assert res['pos'] != (-1, -1)
                return res['pos'], res['lost']
        return None, False
    def shoot(self, pos) -> tuple[bool, dict, bool]:
        res = self._makeReq(COM.SHOOT, {'pos': pos})
        return res['hitted'], res['whole_ship'], res['game_won']
    
    # internals -------------------------------------
    def _makeReq(self, command: COM, payload: dict=dict(), *, updateTimer:str='') -> dict:
        conn = self._newServerSocket()
        ConnectionPrimitives.send(conn, self.id, command, payload)

        id, recvdCommand, payload = ConnectionPrimitives.recv(conn)
        conn.close()
        assert recvdCommand == command, 'Response should have the same command'
        assert self.id == id or command == COM.CONNECT, 'The received id is not my id'
        if updateTimer:
            self.timers[updateTimer] = time.time()
        return payload
    def _newServerSocket(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(self.SERVER_ADDRES)
        return s
    def _connect(self):
        # TODO: if the server doesn't exist on the addr then this hangs
        res = self._makeReq(COM.CONNECT)
        self.id = res['id']
