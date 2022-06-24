import socket, json, logging
import pickle

# header fields ----------------------------
MSGLEN_SIZE = 8

def send(conn: socket.socket, id: int, command: str, payload: dict={}):
    assert isinstance(payload, dict)
    logging.debug(f'sending req: id {id}, command {command} payload {payload}')
    msg = {
        'id': id, 
        'command': command, 
        'payload': payload
    }
    msg = json.dumps(msg)
    byteArr = bytearray(len(msg).to_bytes(MSGLEN_SIZE, byteorder='big'))
    byteArr.extend(msg.encode('utf-8'))
    conn.sendall(byteArr)
    conn.shutdown(socket.SHUT_WR)

def recv(conn: socket.socket) -> tuple[int, str, dict]:
    responseLen = int.from_bytes(_recvBytes(conn, MSGLEN_SIZE), byteorder='big')

    response = _recvBytes(conn, responseLen).decode('utf-8')
    response = json.loads(response)

    conn.shutdown(socket.SHUT_RD)
    id, command, payload = [response[x] for x in ['id', 'command', 'payload']]
    logging.debug(f'received req: id {id}, command {command} payload {payload}')
    return id, command, payload

def _recvBytes(conn, num) -> bytes:
    '''makes sure that self.response has at least num bytes'''
    numRecvd = 0
    response = bytearray(0)
    while numRecvd < num:
        recvd = conn.recv(min(2048, num-numRecvd))
        response += recvd
        numRecvd += len(recvd)
    return response
