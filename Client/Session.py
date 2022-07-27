import socket, time
from Shared import ConnectionPrimitives
from Shared.Enums import COM
from queue import Queue, Empty
import threading
import enum, typing

class Session:
    SERVER_ADDRES = ('192.168.0.159', 1250)
    TIME_BETWEEN_REQUESTS = 1.0
    
    def __init__(self):
        self.connected = False
        self.id: int = 0
        self.stayConnected: bool = True
        self.timers: dict[str, float] = {}
        self.resetAllTimers()

        self.reqQueue: Queue[tuple[str, dict, typing.Callable]] = Queue()
        self.responseList: list[tuple[dict, typing.Callable]] = []
        self.responseLock = threading.Lock()
        self.endEvent = threading.Event()
        self.reqThread = threading.Thread(target=self.reqLoop)
        self.reqThread.start()
        
        self._connect()
    def resetTimer(self, timer: str):
        self.timers[timer] = 0.0
    def resetAllTimers(self):
        self.timers = {COM.CONNECTION_CHECK: 0.0, COM.PAIR: 0.0, COM.GAME_WAIT: 0.0, COM.OPPONENT_SHOT: 0.0}
    def close(self):
        self.endEvent.set()
        self.reqThread.join()
        self._makeReq(COM.DISCONNECT)
    def ensureConnection(self, callback):
        if self.timers[COM.CONNECTION_CHECK] < time.time()-self.TIME_BETWEEN_REQUESTS:
            self.putReq(COM.CONNECTION_CHECK, {}, callback)
            self.timers[COM.CONNECTION_CHECK] = time.time()

    def lookForOpponent(self, callback):
        if self.timers[COM.PAIR] < time.time()-self.TIME_BETWEEN_REQUESTS:
            self.putReq(COM.PAIR, {}, callback)
            self.timers[COM.PAIR] = time.time()

    def sendReadyForGame(self, state: dict):
        ret = self._makeReq(COM.GAME_READINESS, state) # TODO: this one is not async
        return ret['approved']
    def waitForGame(self, callback) -> tuple[bool, bool]:
        if self.timers[COM.GAME_WAIT] < time.time()-self.TIME_BETWEEN_REQUESTS:
            self.putReq(COM.GAME_WAIT, {}, callback)
    def opponentShot(self, callback) -> tuple[tuple[int, int], bool]:
        if self.timers[COM.OPPONENT_SHOT] < time.time()-self.TIME_BETWEEN_REQUESTS:
            self.putReq(COM.OPPONENT_SHOT, {}, callback)
    def shoot(self, pos, callback) -> tuple[bool, dict, bool]:
        self.putReq(COM.SHOOT, {'pos': pos}, callback)

    def loadResponses(self):
        self.responseLock.acquire()
        ress = self.responseList
        self.responseList = []
        self.responseLock.release()

        for res, callback in ress:
            callback(res)

    # multithreaded ------------------------------------
    def reqLoop(self):
        # TODO: handle requests asyncly
        while not self.endEvent.is_set():
            try:
                command, payload, callback = self.reqQueue.get(timeout=1)
                res = self._makeReq(command, payload)
                self.responseLock.acquire()
                self.responseList.append((res, callback))
                self.responseLock.release()
            except Empty:
                pass
    
    def putReq(self, command, payload, callback):
        assert isinstance(command, enum.Enum) and isinstance(payload, dict) and callable(callback), 'the request is not as expected'
        if self.connected or command == COM.CONNECT:
            self.reqQueue.put((command, payload, callback))

    # internals -------------------------------------
    def _makeReq(self, command: COM, payload: dict=dict(), *, updateTimer:str='') -> dict:
        conn = self._newServerSocket()
        ConnectionPrimitives.send(conn, self.id, command, payload)

        id, recvdCommand, payload = ConnectionPrimitives.recv(conn)
        conn.close()
        assert recvdCommand == command, 'Response should have the same command'
        assert self.id == id or command == COM.CONNECT, 'The received id is not my id'
        if updateTimer:
            self.timers[updateTimer] = time.time()
        return payload
    def _newServerSocket(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(self.SERVER_ADDRES)
        return s
    def _connect(self):
        # TODO: if the server doesn't exist on the addr then this hangs
        res = self._makeReq(COM.CONNECT) # TODO: this is not async
        self.id = res['id']
        self.connected = True
