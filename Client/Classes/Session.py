import socket, pickle, time

# TODO: closing this hazel
class Session:
    def __init__(self):
        # connect to the server
        # store session id opponents configuration
        # game state
        self.pendingReqs: list[PendingReq] = [] # TODO: use this for async requests
        self.lastTime = 0.0
    def close(self):
        pass
    def handshake(self):
        pass
    def makeReq(self, command, payload=None):
        req = PendingReq(command, payload)
        print(f'[INFO] sending request {command}')
        req.send()

        res = req.recv()
        print(f'[INFO] received {res[0]}')
        return res
    
    def handleConn(self):
        '''this is the function called for checking the state of connection'''
        if self.lastTime < time.time()-2.0:
            self.makeReq('!CONNECTION_CHECK')
            self.lastTime = time.time()


    
class PendingReq:
    HEADER_LEN_SIZE = 8
    HEADER_COMMAND_SIZE = 32
    SERVER_ADDRES = ('192.168.0.159', 1250)

    def __init__(self, command: str, payload: object = None):
        self.conn: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
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
        byteArr.extend(self.command.encode('utf-8'))
        assert len(byteArr) <= self.HEADER_COMMAND_SIZE+self.HEADER_LEN_SIZE, f'Command is too big to fit in the header, it\'s size is {len(byteArr)} bytes'
        byteArr += bytes(self.HEADER_COMMAND_SIZE+self.HEADER_LEN_SIZE - len(byteArr))
        return byteArr

    def recv(self) -> tuple[str, object]:
        self.recvBytes(self.HEADER_LEN_SIZE+self.HEADER_COMMAND_SIZE)
        payloadLen = int.from_bytes(self.response[:self.HEADER_LEN_SIZE], byteorder='big')

        command = self.response[self.HEADER_LEN_SIZE:self.HEADER_LEN_SIZE+self.HEADER_COMMAND_SIZE]
        command = command.rstrip(bytes(1)).decode('utf-8')

        self.recvBytes(self.HEADER_LEN_SIZE+self.HEADER_COMMAND_SIZE+payloadLen)
        self.conn.close()
        payload = self.response[self.HEADER_LEN_SIZE+self.HEADER_COMMAND_SIZE:]
        payload = pickle.loads(payload)     
        return command, payload
    def recvBytes(self, num : int):
        '''makes sure that self.response has at least num bytes'''
        while self.recvd < num:
            recvd = self.conn.recv(min(2048, num-self.recvd))
            self.response += recvd
            self.recvd += len(recvd)
