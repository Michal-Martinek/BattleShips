import socket, time
from Shared import ConnectionPrimitives
from Shared.Enums import COM
from queue import Queue, Empty
import threading
import logging
import enum, typing

# helpers
def iterQueue(q: Queue):
        try:
            while 1:
                yield q.get_nowait()
        except Empty:
            return

SERVER_ADDRES = ('192.168.0.159', 1250)
MAX_TIME_BETWEEN_CONNECTION_CHECKS = 23.0

class Session:    
    def __init__(self):
        self.id: int = 0
        self.alreadySent: dict[COM, bool] = {COM.CONNECT: False, COM.CONNECTION_CHECK: False, COM.PAIR: False, COM.GAME_READINESS: False, COM.GAME_WAIT: False, COM.SHOOT: False, COM.OPPONENT_SHOT: False, COM.DISCONNECT: False}
        self.lastReqTime = 0.0
        self.connected = False
        self.properlyClosed = False

        self.reqQueue: Queue[tuple[COM, dict, typing.Callable, bool]] = Queue() # TODO: make a dataclass for requests
        self.requestsToRecv: Queue[tuple[socket.socket, COM, typing.Callable]] = Queue()
        self.responseQueue: Queue[tuple[dict, typing.Callable, COM]] = Queue()
        self.quitNowEvent = threading.Event()

        self.sendThread = threading.Thread(target=self.sendLoop, name='Thread-Send')
        self.sendThread.start()
        self.recvThread = threading.Thread(target=self.recvLoop, name='Thread-Recv')
        self.recvThread.start()
    
    def setAlreadySent(self, comm: COM):
        assert not self.alreadySent[comm]
        self.alreadySent[comm] = True
    def resetAlreadySent(self, comm: COM):
        assert self.alreadySent[comm]
        self.alreadySent[comm] = False
    def noPendingReqs(self):
        return not any(self.alreadySent.values())
    
    # api --------------------------------------    
    def tryToSend(self, command: COM, payload: dict, callback: typing.Callable, *, blocking: bool, mustSend=False) -> bool:
        '''sends the req if it wasn't already sent
        on unsuccesfull send if 'mustSend' it raises RuntimeError, the 'mustSend' best works for requests which post data to the server'''
        if sent := not self.alreadySent[command]:
            self._putReq(command, payload, callback, blocking=blocking)
            self.setAlreadySent(command)
        elif mustSend:
            raise RuntimeError("Request specified with 'mustSent' could not be sent due to request being already sent")
        return sent

    def loadResponses(self, *, _drain=False) -> bool:
        '''gets all available responses and calls callbacks
        the parameter '_drain' should only be used internally'''
        if self.quitNowEvent.is_set(): return False
        self.checkThreads()
        stayConnected = True
        for res, callback, command in iterQueue(self.responseQueue):
            stayConnected = stayConnected and res['stay_connected']
            if not _drain: callback(res)
            self.resetAlreadySent(command)
            self.reqQueue.task_done()
        return stayConnected
    def _putReq(self, command: COM, payload: dict, callback: typing.Callable, *, blocking: bool):
        assert isinstance(command, enum.Enum) and isinstance(command, str) and isinstance(payload, dict) and callable(callback), 'the request does not meet expected properties'
        assert self.connected or command == COM.CONNECT, 'the session is not conected'
        assert self.id != 0 or command == COM.CONNECT, 'self.id is invalid for sending this request'
        self.lastReqTime = time.time()
        self.reqQueue.put((command, payload, callback, blocking))
    # checks and closing -----------------------
    def spawnConnectionCheck(self):
        if self.noPendingReqs() and self.connected:
            self.tryToSend(COM.CONNECTION_CHECK, {}, lambda res: None, blocking=True)
    def disconnect(self):
        assert self.connected
        self.tryToSend(COM.DISCONNECT, {}, lambda res: None, blocking=False, mustSend=True)
        self.connected = False
    def _awaitNoPendingReqs(self):
        '''drains all responses untill there are no pending requests'''
        while not self.noPendingReqs():
            self.loadResponses(_drain=True)
    def quit(self, must=False):
        '''tries to close session, if 'must' it blocks untill closed
          if it gets to actually closing, the disconnect must have been sent in advance'''
        if not self.properlyClosed:
            if self.noPendingReqs() or must:
                self._awaitNoPendingReqs()
                assert not self.connected, 'the session is still connected'
                self.quitNowEvent.set()
                self.properlyClosed = self.joinThreads(must=must)
                if must: assert self.properlyClosed
    def joinThreads(self, must) -> bool:
        tmout = None if must else 0.0
        self.sendThread.join(timeout=tmout)
        if self.sendThread.is_alive(): return False
        self.recvThread.join(timeout=tmout)
        if self.recvThread.is_alive(): return False
        return True
    def checkThreads(self):
        if not self.sendThread.is_alive():
            raise RuntimeError('Thread-Send ended')
        if not self.recvThread.is_alive():
            raise RuntimeError('Thread-Recv ended')
    # request handling running in threads -------------------------------------
    def sendLoop(self):
        '''waits for reqs from main_thread, sends them and then:
        - _fetchResponse for the nonblocking
        - move to Thread-Recv for the blocking'''
        while not self.quitNowEvent.is_set(): # TODO: better handling of the main thread's death
            try:
                command, payload, callback, blocking = self.reqQueue.get(timeout=1.)
                conn = self._sendReq(command, payload)
                if blocking:
                    self.requestsToRecv.put((conn, command, callback))
                else:
                    self._fetchResponse(conn, command, callback)
            except Empty:
                pass
    def recvLoop(self):
        pendingReqs = []
        while not self.quitNowEvent.is_set():
            try:
                req = self.requestsToRecv.get(timeout=0.1)
                pendingReqs.append(req)
            except Empty:
                pass
            self.tryReceiving(pendingReqs)
    def tryReceiving(self, pendingReqs):
        '''loops through pendingReqs and tries to fetch them'''
        doneReqIndxs = []
        for i, (conn, command, callback) in enumerate(pendingReqs):
            if self._canSocketRecv(conn):
                self._fetchResponse(conn, command, callback)
                doneReqIndxs.append(i)
        for i in doneReqIndxs:
            pendingReqs.pop(i)
    def _fetchResponse(self, conn: socket.socket, command, callback):
        conn.setblocking(True)
        res = self._recvReq(conn, command)
        self.responseQueue.put((res, callback, command))
    @ staticmethod
    def _canSocketRecv(s: socket.socket):
        try:
            s.setblocking(False)
            return s.recv(1, socket.MSG_PEEK)
        except BlockingIOError:
            return False

    # internals -------------------------------------
    def _sendReq(self, command: COM, payload: dict=dict()) -> socket.socket:
        conn = self._newServerSocket()
        ConnectionPrimitives.send(conn, self.id, command, payload)
        return conn
    def _recvReq(self, conn: socket.socket, sentCommand: COM) -> dict:
        id, recvdCommand, payload = ConnectionPrimitives.recv(conn)
        conn.close()
        assert recvdCommand == sentCommand, 'Response should have the same command'
        assert self.id == id or sentCommand == COM.CONNECT, 'The received id is not my id'
        return payload
    def _newServerSocket(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(SERVER_ADDRES)
        return s
