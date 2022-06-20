import socket, pickle, random

# import Game

HEADER_LEN_SIZE = 8
HEADER_COMMAND_SIZE = 32
HEADER_ID_SIZE = 8

ID = int

class ConnectedPlayer:
    def __init__(self, id):
        self.id = id

class Server:
    def __init__(self, addr):
        self.serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.serverSocket.bind(addr)
        self.serverSocket.listen()

        self.connectedPlayers: dict[ID, ConnectedPlayer] = dict()

    @ staticmethod
    def recvBytes(conn, numBytes):
        res = bytearray(0)
        while len(res) < numBytes:
            res += conn.recv(min(2048, numBytes-len(res)))
        return res

    def constructHeader(self, msgLen, id, command) -> bytearray:
        byteArr = bytearray(msgLen.to_bytes(8, byteorder='big'))
        byteArr.extend(id.to_bytes(8, byteorder='big'))
        byteArr.extend(command.encode('utf-8'))
        assert len(byteArr) <= HEADER_COMMAND_SIZE+HEADER_LEN_SIZE+HEADER_ID_SIZE, f'Command is too big to fit in the header, it\'s size is {len(byteArr)} bytes'
        byteArr += bytes(HEADER_COMMAND_SIZE+HEADER_LEN_SIZE+HEADER_ID_SIZE - len(byteArr))
        return byteArr
    def send(self, conn, id, command, payload=None):
        msg = pickle.dumps(payload)
        byteArr = self.constructHeader(len(msg), id, command)
        byteArr.extend(msg)
        conn.sendall(byteArr)
        conn.shutdown(socket.SHUT_RDWR)
        # TODO: close?

    def handleQuery(self, conn: socket.socket):
        header = conn.recv(HEADER_LEN_SIZE+HEADER_ID_SIZE+HEADER_COMMAND_SIZE)
        payloadLen = int.from_bytes(header[:HEADER_LEN_SIZE], byteorder='big')

        id = int.from_bytes(header[HEADER_LEN_SIZE:HEADER_LEN_SIZE+HEADER_ID_SIZE], byteorder='big')

        command = header[HEADER_LEN_SIZE+HEADER_ID_SIZE:HEADER_LEN_SIZE+HEADER_ID_SIZE+HEADER_COMMAND_SIZE]
        command = command.rstrip(bytes(1)).decode('utf-8')

        payload = self.recvBytes(conn, payloadLen)
        payload = pickle.loads(payload)

        print(f'[DEBUG] id {id} command {command}\npayload {payload}')
        
        if command == '!CONNECT' and payload == None:
            print('[INFO] connecting new player', conn.getpeername())
            player = self.newConnectedPlayer()
            self.connectedPlayers[player.id] = player
            self.send(conn, id, '!CONNECTED', player.id)
            
        elif command == '!CONNECTION_CHECK' and payload == None:
            self.send(conn, id, '!CONNECTION_CHECK_RES')
        elif command == '!DISCONNECT' and payload == None:
            self.send(conn, id, '!DISCONNECT')
            exit(1)
        else:
            print(f'[ERROR] {command}: {payload}')
            assert False, 'unreachable'
    
    def loop(self):
        while True:
            conn, addr = self.serverSocket.accept()
            print(f'[INFO] got query from {addr}')
            self.handleQuery(conn)

    def newConnectedPlayer(self):
        id = self.generateNewID()
        return ConnectedPlayer(id)

    def generateNewID(self):
        bounds = (1000, 2**20)
        id = random.randint(*bounds)
        while id in self.connectedPlayers:
            id = random.randint(*bounds)
        return id
    def connectPlayer(self, conn, addr):
        player = self.newConnectedPlayer()
        print('new player connected', player.id, 'from', *conn.getpeername())
        # TODO: send connection response
        

    def pairPlayers(self):
        while len(self.connectedPlayers) >= 2:
            players = [self.connectedPlayers.pop() for _ in range(2)]
            # self.startGameSession(players)

    # def startGameSession(self, players):
    #     gameObj = Game.Game(players)
    #     thread = threading.Thread(target=gameObj.game)
    #     thread.start()
    #     self.activeGames.append(thread)

def serverMain():
    ADDR = (socket.gethostbyname(socket.gethostname()), 1250)
    server = Server(ADDR)
    print(f'server ready and listening at {ADDR[0]}:{ADDR[1]}')
    server.loop()
    
    
if __name__ == '__main__':
    serverMain()
