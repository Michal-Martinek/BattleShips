import socket, time
import sys, os
sys.path.append(os.path.join(os.path.split(sys.path[0])[0], 'Shared'))
import ConnectionPrimitives # type:ignore

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
    def ensureConnection(self):
        if self.lastTime < time.time()-2.0:
            command, _ = self._makeReq('!CONNECTION_CHECK')
            assert command == '!CONNECTION_CHECK_RES'
    def lookForOpponent(self) -> bool:
        if self.lastTime < time.time()-2.0:
            command, res = self._makeReq('!PAIR_REQ')
            if command == '!UNPAIRED':
                return False
            elif command == '!PAIRED':
                self.inGame = True
                self.opponentId = res['opponent_id']
                return True
            else:
                assert False, 'unreachable'
            
    # internals -------------------------------------
    def _makeReq(self, command, payload: dict=dict()):
        conn = self._newServerSocket()
        ConnectionPrimitives.send(conn, self.id, command, payload)

        id, command, payload = ConnectionPrimitives.recv(conn)
        conn.close()
        assert self.id == id
        print(f'[INFO] received {command} {payload}')
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
