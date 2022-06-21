import socket, time
import sys, os
sys.path.append(os.path.join(os.path.split(sys.path[0])[0], 'Shared'))
import ConnectionPrimitives # type:ignore

class Session:
    SERVER_ADDRES = ('192.168.0.159', 1250)
    def __init__(self):
        self.id = 0
        self._connect()
        self.lastTime = 0.0
    def close(self):
        self._makeReq('!DISCONNECT')
    def handleConn(self):
        '''this is the function called for checking the state of connection'''
        if self.lastTime < time.time()-2.0:
            command, _ = self._makeReq('!CONNECTION_CHECK')
            assert command == '!CONNECTION_CHECK_RES'
            self.lastTime = time.time()
    # internals -------------------------------------
    def _makeReq(self, command, payload: dict=dict()):
        conn = self._newServerSocket()
        ConnectionPrimitives.send(conn, self.id, command, payload)

        id, command, payload = ConnectionPrimitives.recv(conn)
        conn.close()
        assert self.id == id
        print(f'[INFO] received {command} {payload}')
        return command, payload
    def _newServerSocket(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(self.SERVER_ADDRES)
        return s
    def _connect(self):
        command, res = self._makeReq('!CONNECT')
        assert command == '!CONNECTED'
        self.id = res['id']
