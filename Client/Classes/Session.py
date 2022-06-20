import socket, pickle, time

class Session:
    def __init__(self):
        # connect to the server
        # store session id opponents configuration
        # game state
        # self.pendingReqs: list[PendingReq] = [] # TODO: use this for async requests
        self.id = 0
        self.connect()
        self.lastTime = 0.0
    def close(self):
        self.makeReq('!DISCONNECT')
    def handshake(self):
        pass
    def makeReq(self, command, payload=None):
        req = PendingReq(self.id, command, payload)
        print(f'[INFO] sending request {command}')
        req.send()

        command, payload = req.recv()
        print(f'[INFO] received {command} {payload}')
        return command, payload
    
    def handleConn(self):
        '''this is the function called for checking the state of connection'''
        if self.lastTime < time.time()-2.0:
            command, _ = self.makeReq('!CONNECTION_CHECK')
            assert command == '!CONNECTION_CHECK_RES'
            self.lastTime = time.time()

    def connect(self):
        command, id = self.makeReq('!CONNECT')
        assert command == '!CONNECTED'
        self.id = id
    
class PendingReq:
    HEADER_LEN_SIZE = 8
    HEADER_COMMAND_SIZE = 32
    HEADER_ID_SIZE = 8
    SERVER_ADDRES = ('192.168.0.159', 1250)

    def __init__(self, id: int, command: str, payload: object = None):
        self.conn: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.id = id
        self.command: str = command
        self.payload: object = payload
        self.response: bytearray = bytearray()
        self.recvd: int = 0
        self.sent: bool = False

    def send(self):
        self.conn.connect(self.SERVER_ADDRES)
        msg = pickle.dumps(self.payload)
        byteArr = self.constructHeader(len(msg))
        byteArr.extend(msg)
        self.conn.sendall(byteArr)
        self.sent = True
        self.conn.shutdown(socket.SHUT_WR)
    def constructHeader(self, msgLen) -> bytearray:
        byteArr = bytearray(msgLen.to_bytes(8, byteorder='big'))
        byteArr.extend(self.id.to_bytes(8, byteorder='big'))
        byteArr.extend(self.command.encode('utf-8'))
        assert len(byteArr) <= self.HEADER_ID_SIZE+self.HEADER_COMMAND_SIZE+self.HEADER_LEN_SIZE, f'Command is too big to fit in the header, it\'s size is {len(byteArr)} bytes'
        byteArr += bytes(self.HEADER_ID_SIZE+self.HEADER_COMMAND_SIZE+self.HEADER_LEN_SIZE - len(byteArr))
        return byteArr

    def recv(self) -> tuple[str, object]:
        self.recvBytes(self.HEADER_LEN_SIZE+self.HEADER_COMMAND_SIZE+self.HEADER_ID_SIZE)
        payloadLen = int.from_bytes(self.response[:self.HEADER_LEN_SIZE], byteorder='big')

        id = self.response[self.HEADER_LEN_SIZE:self.HEADER_LEN_SIZE+self.HEADER_ID_SIZE]
        id = int.from_bytes(id, byteorder='big')
        print('[DEBUG] the id of received', repr(id), repr(self.id))
        assert self.id == id

        command = self.response[self.HEADER_LEN_SIZE+self.HEADER_ID_SIZE:self.HEADER_LEN_SIZE+self.HEADER_ID_SIZE+self.HEADER_COMMAND_SIZE]
        command = command.rstrip(bytes(1)).decode('utf-8')

        self.recvBytes(self.HEADER_LEN_SIZE+self.HEADER_ID_SIZE+self.HEADER_COMMAND_SIZE+payloadLen)
        self.conn.shutdown(socket.SHUT_RD)
        self.conn.close()
        payload = self.response[self.HEADER_LEN_SIZE+self.HEADER_ID_SIZE+self.HEADER_COMMAND_SIZE:]
        payload = pickle.loads(payload)     
        return command, payload
    def recvBytes(self, num : int):
        '''makes sure that self.response has at least num bytes'''
        while self.recvd < num:
            recvd = self.conn.recv(min(2048, num-self.recvd))
            self.response += recvd
            self.recvd += len(recvd)
