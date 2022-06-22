import socket, time
from Shared import ConnectionPrimitives

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
        self._makeReq('!DISCONNECT')
    # TODO: maybe it would be useful to have a function which would make a request periodically after some time
    def ensureConnection(self) -> bool:
        if self.lastTime < time.time()-2.0:
            command, _ = self._makeReq('!CONNECTION_CHECK', updateTime=True)
            if command == '!CONNECTION_CHECK_RES':
                return True
            elif command == '!OPPONENT_DISCONNECTED':
                return False
            else:
                assert False, 'unreachable'
        return True
    def lookForOpponent(self) -> bool:
        if self.lastTime < time.time()-2.0:
            command, res = self._makeReq('!PAIR_REQ', updateTime=True)
            if command == '!UNPAIRED':
                return False
            elif command == '!PAIRED':
                self.inGame = True
                self.opponentId = res['opponent_id']
                return True
            else:
                assert False, 'unreachable'
            
    # internals -------------------------------------
    def _makeReq(self, command, payload: dict=dict(), *, updateTime=False):
        conn = self._newServerSocket()
        ConnectionPrimitives.send(conn, self.id, command, payload)

        id, command, payload = ConnectionPrimitives.recv(conn)
        conn.close()
        assert self.id == id or command == '!CONNECTED', 'The received id is not my id'
        if updateTime:
            self.lastTime = time.time()
        return command, payload
    def _newServerSocket(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(self.SERVER_ADDRES)
        return s
    def _connect(self):
        command, res = self._makeReq('!CONNECT')
        assert command == '!CONNECTED'
        self.id = res['id']
