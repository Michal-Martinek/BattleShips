import socket, time
from Shared import ConnectionPrimitives
from Shared.Enums import COM
from queue import Queue, Empty
import threading
import logging
import enum, typing

class Session:
    SERVER_ADDRES = ('192.168.0.159', 1250)
    TIME_BETWEEN_REQUESTS = 1.0
    
    def __init__(self):
        self.connected = False
        self.id: int = 0
        self.timers: dict[str, float] = {}
        self.resetAllTimers()

        self.blockReqs = False

        self.reqQueue: Queue[tuple[str, dict, typing.Callable, bool]] = Queue()
        self.responseList: list[tuple[dict, typing.Callable, bool]] = []
        self.responseLock = threading.Lock()
        self.endEvent = threading.Event()
        self.reqThread = threading.Thread(target=self.reqLoop)
        self.reqThread.start()
        
    def setTimer(self, timer: str):
        self.timers[timer] = time.time()
    def resetAllTimers(self):
        self.timers = {COM.CONNECTION_CHECK: 0.0, COM.PAIR: 0.0, COM.GAME_WAIT: 0.0, COM.OPPONENT_SHOT: 0.0}
    def shouldSend(self, timer: str):
        return self.timers[timer] < time.time()-self.TIME_BETWEEN_REQUESTS

    def sendBlockingReq(self, command: COM, payload: dict, callback: typing.Callable, *, block=False) -> bool:
        if self.shouldSend(command):
            put = self.putReq(command, payload, callback, block=block)
            if put:
                self.setTimer(command)
                return True
        return False
    
    def sendNonblockingReq(self, command: COM, payload: dict, callback: typing.Callable, *, block=True):
        put = self.putReq(command, payload, callback, block=block, mustBePut=True)
        self.resetAllTimers()
        assert put, 'non blocking requests should always be putted'

    # TODO: these are not async
    def close(self):
        logging.debug('joining the requests Thread and disconnecting from the server')
        self.endEvent.set()
        self.reqThread.join()
        self._makeReq(COM.DISCONNECT)

    # multithreaded ------------------------------------
    def loadResponses(self):
        self.responseLock.acquire()
        ress = self.responseList
        self.responseList = []
        self.responseLock.release()

        for res, callback, block in ress:
            callback(res)
            if block:
                self.blockReqs = False

    def reqLoop(self):
        # TODO: handle requests asyncly
        while not self.endEvent.is_set() and threading.main_thread().is_alive():
            try:
                command, payload, callback, block = self.reqQueue.get(timeout=0.2)
                res = self._makeReq(command, payload)
                self.responseLock.acquire()
                self.responseList.append((res, callback, block))
                self.responseLock.release()
                self.reqQueue.task_done()
            except Empty:
                pass
    
    def putReq(self, command, payload, callback, *, block=False, mustBePut=False) -> bool:
        '''@return - True if the request was properly put to the request queue'''
        assert isinstance(command, enum.Enum) and isinstance(payload, dict) and callable(callback), 'the request is not as expected'
        if not self.blockReqs or mustBePut:
            if block:
                self.blockReqs = True # TODO: the request blocking is weird
                self.reqQueue.join()
            self.reqQueue.put((command, payload, callback, block))
            return True
        return False

    # internals -------------------------------------
    def _makeReq(self, command: COM, payload: dict=dict()) -> dict:
        conn = self._newServerSocket()
        ConnectionPrimitives.send(conn, self.id, command, payload)

        id, recvdCommand, payload = ConnectionPrimitives.recv(conn)
        conn.close()
        assert recvdCommand == command, 'Response should have the same command'
        assert self.id == id or command == COM.CONNECT, 'The received id is not my id'
        return payload
    def _newServerSocket(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(self.SERVER_ADDRES)
        return s
