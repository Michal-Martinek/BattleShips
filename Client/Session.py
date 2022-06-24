import socket, time
from Shared import ConnectionPrimitives
from Shared.CommandNames import *

class Session:
    SERVER_ADDRES = ('192.168.0.159', 1250)
    def __init__(self):
        self.id = 0
        self.inGame = False
        self.opponentId = 0
        self.lastTime = 0.0
        
        self._connect()
    def resetTimer(self):
        self.lastTime = 0.0
    def close(self):
        self._makeReq(COM_DISCONNECT)
    # TODO: maybe it would be useful to have a function which would make a request periodically after some time
    def ensureConnection(self) -> bool:
        if self.lastTime < time.time()-2.0:
            payload = self._makeReq(COM_CONNECTION_CHECK, updateTime=True)
            return payload['still_ingame']
        return True
    def lookForOpponent(self) -> bool:
        if self.lastTime < time.time()-2.0:
            res = self._makeReq(COM_PAIR, updateTime=True)
            if res['paired']:
                self.inGame = True
                self.opponentId = res['opponent_id']
            return res['paired']
    def sendGameInfo(self, d: dict):
        self._makeReq(COM_BOARD_STATE, d)
    def recvGameInfo(self):
        return self._makeReq(COM_OPPONENT_INFO)
            
    # internals -------------------------------------
    def _makeReq(self, command, payload: dict=dict(), *, updateTime=False) -> dict:
        conn = self._newServerSocket()
        ConnectionPrimitives.send(conn, self.id, command, payload)

        id, recvdCommand, payload = ConnectionPrimitives.recv(conn)
        conn.close()
        assert recvdCommand == command, 'Response should have the same command'
        assert self.id == id or command == COM_CONNECT, 'The received id is not my id'
        if updateTime:
            self.lastTime = time.time()
        return payload
    def _newServerSocket(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(self.SERVER_ADDRES)
        return s
    def _connect(self):
        res = self._makeReq(COM_CONNECT)
        self.id = res['id']
