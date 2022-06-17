import socket, threading, pickle

# import Game
# from Session import PlayerSession

HEADER_LEN_SIZE = 8
HEADER_COMMAND_SIZE = 32

class Server:
    def __init__(self, addr):
        self.serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.serverSocket.bind(addr)
        self.serverSocket.listen()

        # self.activeGames = []
        # self.unpairedPlayers : list[PlayerSession] = []

    @ staticmethod
    def recvBytes(conn, numBytes):
        res = bytearray(0)
        while len(res) < numBytes:
            res += conn.recv(min(2048, numBytes-len(res)))
        return res

    def constructHeader(self, msgLen, command) -> bytearray:
        byteArr = bytearray(msgLen.to_bytes(8, byteorder='big'))
        byteArr.extend(command.encode('utf-8'))
        assert len(byteArr) <= HEADER_COMMAND_SIZE+HEADER_LEN_SIZE, f'Command is too big to fit in the header, it\'s size is {len(byteArr)} bytes'
        byteArr += bytes(HEADER_COMMAND_SIZE+HEADER_LEN_SIZE - len(byteArr))
        return byteArr
    def send(self, conn, command, payload=None):
        msg = pickle.dumps(payload)
        byteArr = self.constructHeader(len(msg), command)
        byteArr.extend(msg)
        conn.sendall(byteArr)
        conn.shutdown(socket.SHUT_RDWR)
        # TODO: close?
    
    def loop(self):
        while True:
            conn, addr = self.serverSocket.accept()
            print(f'[INFO] got connection from {addr}')
            header = conn.recv(HEADER_LEN_SIZE+HEADER_COMMAND_SIZE)
            payloadLen = int.from_bytes(header[:HEADER_LEN_SIZE], byteorder='big')

            command = header[HEADER_LEN_SIZE:HEADER_LEN_SIZE+HEADER_COMMAND_SIZE]
            command = command.rstrip(bytes(1)).decode('utf-8')

            payload = self.recvBytes(conn, payloadLen)
            payload = pickle.loads(payload)
            
            if command == '!CONNECTION_CHECK' and payload == None:
                self.send(conn, '!CONNECTION_CHECK_RES')
            else:
                print(f'[INFO] {command}: {payload}')
                assert False, 'unreachable'
            
            # self.acceptConn(conn, addr)
            # self.pairPlayers()
    
    # def acceptConn(self, conn, addr):
    #     player = PlayerSession(conn, addr)
    #     print('player connected', player.getAddrStr())
    #     self.unpairedPlayers.append(player)
    #     # TODO: send connection response
        

    # def pairPlayers(self):
    #     while len(self.unpairedPlayers) >= 2:
    #         players = [self.unpairedPlayers.pop() for _ in range(2)]
    #         self.startGameSession(players)

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
