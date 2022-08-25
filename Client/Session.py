import socket, time
from Shared import ConnectionPrimitives
from Shared.Enums import COM
from queue import Queue, Empty
import threading
import logging
from dataclasses import dataclass
import enum, typing

# helpers
AnyT = typing.TypeVar('AnyT')
def iterQueue(q: Queue[AnyT]) -> typing.Iterator[AnyT]:
        try:
            while 1:
                yield q.get_nowait()
        except Empty:
            return
@ dataclass
class Request:
    command: COM
    payload: dict
    callback: typing.Callable
    blocking: bool
    conn: socket.socket=None
    state: int=0 # 0 - waiting, 1- sent, 2 - received


SERVER_ADDRES = ('192.168.0.159', 1250)
MAX_TIME_BETWEEN_CONNECTION_CHECKS = 23.0

class Session:    
    def __init__(self):
        self.id: int = 0
        self.alreadySent: dict[COM, bool] = {COM.CONNECT: False, COM.CONNECTION_CHECK: False, COM.PAIR: False, COM.GAME_READINESS: False, COM.GAME_WAIT: False, COM.SHOOT: False, COM.OPPONENT_SHOT: False, COM.DISCONNECT: False}
        self.lastReqTime = 0.0
        self.connected = False
        self.properlyClosed = False

        self.reqQueue: Queue[Request] = Queue()
        self.requestsToRecv: Queue[Request] = Queue()
        self.responseQueue: Queue[Request] = Queue()
        self.quitNowEvent = threading.Event()

        self.sendThread = threading.Thread(target=self.sendLoop, name='Thread-Send', daemon=True) # TODO: sometimes after keyboard imterrupt some thread just hangs
        self.sendThread.start()
        self.recvThread = threading.Thread(target=self.recvLoop, name='Thread-Recv', daemon=True)
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
        for req in iterQueue(self.responseQueue):
            stayConnected = stayConnected and req.payload['stay_connected']
            if not _drain: req.callback(req.payload)
            self.resetAlreadySent(req.command)
            self.reqQueue.task_done()
        return stayConnected
    def _putReq(self, command: COM, payload: dict, callback: typing.Callable, *, blocking: bool):
        assert isinstance(command, enum.Enum) and isinstance(command, str) and isinstance(payload, dict) and callable(callback), 'the request does not meet expected properties'
        assert self.connected or command == COM.CONNECT, 'the session is not conected'
        assert self.id != 0 or command == COM.CONNECT, 'self.id is invalid for sending this request'
        self.lastReqTime = time.time()
        self.reqQueue.put(Request(command, payload, callback, blocking))
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
        while not self.quitNowEvent.is_set():
            try:
                req = self.reqQueue.get(timeout=1.)
                self._sendReq(req)
                if req.blocking:
                    self.requestsToRecv.put(req)
                else:
                    self._fetchResponse(req)
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
    def _fetchResponse(self, req: Request):
        self._recvReq(req)
        self.responseQueue.put(req)
    @ staticmethod
    def _canSocketRecv(s: socket.socket):
        try:
            s.setblocking(False)
            return s.recv(1, socket.MSG_PEEK)
        except BlockingIOError:
            return False

    # internals -------------------------------------
    def _sendReq(self, req: Request) -> socket.socket:
        assert req.state == 0
        self._newServerSocket(req)
        ConnectionPrimitives.send(req.conn, self.id, req.command, req.payload)
        req.state = 1
    def _recvReq(self, req: Request):
        assert req.state == 1
        id, recvdCommand, req.payload = ConnectionPrimitives.recv(req.conn)
        req.conn.close()
        req.state = 2
        assert recvdCommand == req.command, 'Response should have the same command'
        assert self.id == id or req.command == COM.CONNECT, 'The received id is not my id'
    def _newServerSocket(self, req: Request):
        req.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        req.conn.connect(SERVER_ADDRES)
