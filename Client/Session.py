import socket, time
from Shared import ConnectionPrimitives
from Shared.CommandNames import *
from . import Game

class Session:
    SERVER_ADDRES = ('192.168.0.159', 1250)
    def __init__(self):
        self.id = 0
        self.inGame = False
        self.opponentId = 0
        self.timers = {}
        self.resetAllTimers()
        
        self._connect()
    def resetTimer(self, timer: str):
        self.timers[timer] = 0.0
    def resetAllTimers(self):
        self.timers = self.timers = {COM_CONNECTION_CHECK: 0.0, COM_PAIR: 0.0, COM_GAME_WAIT: 0.0}
    def close(self):
        self._makeReq(COM_DISCONNECT)
    # TODO: maybe it would be useful to have a function which would make a request periodically after some time
    def ensureConnection(self) -> bool:
        if self.timers[COM_CONNECTION_CHECK] < time.time()-2.0:
            payload = self._makeReq(COM_CONNECTION_CHECK, updateTimer=COM_CONNECTION_CHECK)
            return payload['stay_connected']
        return True
    def lookForOpponent(self) -> bool:
        if self.timers[COM_PAIR] < time.time()-2.0:
            res = self._makeReq(COM_PAIR, updateTimer=COM_PAIR)
            if res['paired']:
                self.inGame = True
                self.opponentId = res['opponent_id']
            return res['paired']
    def sendReadyForGame(self, state: dict):
        ret = self._makeReq(COM_GAME_READINESS, state)
        return ret['approved']
    def waitForGame(self):
        if self.timers[COM_GAME_WAIT] < time.time()-2.0:
            res = self._makeReq(COM_GAME_WAIT, updateTimer=COM_GAME_WAIT)
            if res['started']:
                return res['opponent_state']
        return None
    
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
