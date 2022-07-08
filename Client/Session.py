import socket, time
from Shared import ConnectionPrimitives
from Shared.CommandNames import *

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
        self.timers = {COM_CONNECTION_CHECK: 0.0, COM_PAIR: 0.0, COM_GAME_WAIT: 0.0, COM_OPPONENT_SHOT: 0.0}
    def close(self):
        self._makeReq(COM_DISCONNECT)
    # TODO: maybe it would be useful to have a function which would make a request periodically after some time
    def ensureConnection(self) -> bool:
        if self.timers[COM_CONNECTION_CHECK] < time.time()-self.TIME_BETWEEN_REQUESTS:
            payload = self._makeReq(COM_CONNECTION_CHECK, updateTimer=COM_CONNECTION_CHECK)
            return payload['stay_connected']
        return True
    def lookForOpponent(self) -> bool:
        if self.timers[COM_PAIR] < time.time()-self.TIME_BETWEEN_REQUESTS:
            res = self._makeReq(COM_PAIR, updateTimer=COM_PAIR)
            if res['paired']:
                self.inGame = True
                self.opponentId = res['opponent_id']
            return res['paired']
    def sendReadyForGame(self, state: dict):
        ret = self._makeReq(COM_GAME_READINESS, state)
        return ret['approved']
    def waitForGame(self) -> tuple[dict, bool]:
        if self.timers[COM_GAME_WAIT] < time.time()-self.TIME_BETWEEN_REQUESTS:
            res = self._makeReq(COM_GAME_WAIT, updateTimer=COM_GAME_WAIT)
            if res['started']:
                return res['opponent_state'], res['on_turn'] == self.id
        return None
    def opponentShot(self) -> tuple[int, int]:
        if self.timers[COM_OPPONENT_SHOT] < time.time()-self.TIME_BETWEEN_REQUESTS:
            res = self._makeReq(COM_OPPONENT_SHOT, updateTimer=COM_OPPONENT_SHOT)
            if res['shotted']:
                assert res['pos'] != (-1, -1)
                return res['pos']
        return None
    def shoot(self, pos) -> bool:
        res = self._makeReq(COM_SHOOT, {'pos': pos})
        return res['hitted']
    
    # internals -------------------------------------
    def _makeReq(self, command, payload: dict=dict(), *, updateTimer:str='') -> dict:
        conn = self._newServerSocket()
        ConnectionPrimitives.send(conn, self.id, command, payload)

        id, recvdCommand, payload = ConnectionPrimitives.recv(conn)
        conn.close()
        assert recvdCommand == command, 'Response should have the same command'
        assert self.id == id or command == COM_CONNECT, 'The received id is not my id'
        if updateTimer:
            self.timers[updateTimer] = time.time()
        return payload
    def _newServerSocket(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(self.SERVER_ADDRES)
        return s
    def _connect(self):
        res = self._makeReq(COM_CONNECT)
        self.id = res['id']
