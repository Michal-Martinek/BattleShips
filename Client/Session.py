import socket, time
from queue import Queue, Empty
import threading
import logging

from dataclasses import dataclass
import enum, typing

from Shared import ConnectionPrimitives
from Shared.Enums import COM
from Shared.Helpers import runFuncLogged

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
	state: int=0 # 0 waiting, 1 sent, 2 received

SERVER_ADDRES = ('192.168.0.159', 1250)

class Session:
	def __init__(self):
		self.repeatebleInit()

		self.reqQueue: Queue[Request] = Queue()
		self.requestsToRecv: Queue[Request] = Queue()
		self.responseQueue: Queue[Request] = Queue()
		self.quitNowEvent = threading.Event()

		self.sendThread = threading.Thread(target=lambda: runFuncLogged(self.sendLoop), name='Thread-Send', daemon=True)
		self.sendThread.start()
		self.recvThread = threading.Thread(target=lambda: runFuncLogged(self.recvLoop), name='Thread-Recv', daemon=True)
		self.recvThread.start()
	def repeatebleInit(self):
		self.id: int = 0
		assert len(COM) == 12
		self.alreadySent: dict[COM, bool] = {COM.CONNECT: False, COM.CONNECTION_CHECK: False, COM.PAIR: False, COM.OPPONENT_READY: False, COM.GAME_READINESS: False, COM.GAME_WAIT: False, COM.SHOOT: False, COM.OPPONENT_SHOT: False, COM.DISCONNECT: False, COM.AWAIT_REMATCH: False, COM.UPDATE_REMATCH: False}

	def setAlreadySent(self, comm: COM):
		assert not self.alreadySent[comm]
		self.alreadySent[comm] = True
	def resetAlreadySent(self, comm: COM):
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

	def loadResponses(self, *, _drain=False) -> tuple[str, dict]:
		'''gets all available responses and calls callbacks
		the parameter '_drain' should only be used internally
		@return: game end msg supplied from server, opponent state on game end'''
		if self.quitNowEvent.is_set(): return False
		self.checkThreads()
		stayConnected = True
		gameEndMsg, opponentState = '', None
		for req in iterQueue(self.responseQueue):
			stayConnected &= req.payload['stay_connected']
			if not req.payload['stay_connected']: gameEndMsg = req.payload['game_end_msg']
			if 'opponent_grid' in req.payload: opponentState = req.payload['opponent_grid']
			if not _drain: req.callback(req.payload)
			self.resetAlreadySent(req.command)
			self.reqQueue.task_done()
		self.connected &= stayConnected
		return gameEndMsg, opponentState
	def _putReq(self, command: COM, payload: dict, callback: typing.Callable, *, blocking: bool):
		assert isinstance(command, enum.Enum) and isinstance(command, str) and isinstance(payload, dict) and callable(callback), 'the request does not meet expected properties'
		assert self.connected or command == COM.CONNECT, 'the session is not conected'
		assert self.id != 0 or command == COM.CONNECT, 'self.id is invalid for sending this request'
		self.reqQueue.put(Request(command, payload, callback, blocking))
	# checks and closing -----------------------
	def spawnConnectionCheck(self):
		if self.noPendingReqs() and self.connected:
			self.tryToSend(COM.CONNECTION_CHECK, {}, lambda res: None, blocking=True)
	def disconnect(self):
		assert self.connected
		self.tryToSend(COM.DISCONNECT, {}, lambda res: self.repeatebleInit(), blocking=False, mustSend=True)
	def quit(self):
		'''gracefully closes session (recvs last reqs, joins threads), COM.DISCONNECT must have been sent in advance'''
		while not self.noPendingReqs():
			self.loadResponses(_drain=True)
		assert not self.connected, 'the session is still connected'
		self.quitNowEvent.set()
		self.sendThread.join()
		self.recvThread.join()
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
		pendingReqs: list[Request] = []
		while not self.quitNowEvent.is_set():
			try:
				req = self.requestsToRecv.get(timeout=0.1)
				pendingReqs.append(req)
			except Empty:
				pass
			self.tryReceiving(pendingReqs)
	def tryReceiving(self, pendingReqs: list[Request]):
		'''loops through pendingReqs and tries to fetch them'''
		doneReqs = []
		for req in pendingReqs:
			if self._canSocketRecv(req.conn):
				self._fetchResponse(req)
				doneReqs.append(req)
		for r in doneReqs:
			pendingReqs.remove(r)
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
		if recvdCommand == COM.ERROR:
			logging.error(f'Recvd !ERROR response {req.payload}')
			raise RuntimeError('Recvd !ERROR response')
		assert recvdCommand == req.command, 'Response should have the same command'
		assert self.id == id or req.command == COM.CONNECT, 'The received id is not my id'
	def _newServerSocket(self, req: Request):
		req.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		req.conn.connect(SERVER_ADDRES)
