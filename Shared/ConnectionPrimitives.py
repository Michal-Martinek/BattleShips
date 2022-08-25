import socket, json, logging

DEBUG_REQS = True

MSGLEN_SIZE = 8

def send(conn: socket.socket, id: int, command: str, payload: dict={}):
    assert isinstance(payload, dict)
    if DEBUG_REQS: logging.debug(f'sending req: id {id}, command {command} payload {payload}')
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
    response = recvWholeResponse(conn)
    response = response.decode('utf-8')
    response = json.loads(response)
    id, command, payload = [response[x] for x in ['id', 'command', 'payload']]
    assert isinstance(id, int) and isinstance(command, str) and isinstance(payload, dict)
    if DEBUG_REQS: logging.debug(f'received req: id {id}, command {command} payload {payload}')
    return id, command, payload
def recvWholeResponse(conn: socket.socket):
    res = conn.recv(2048)
    print('len recvd', len(res), res)
    if len(res) < MSGLEN_SIZE:
        res = _recvBytes(conn, MSGLEN_SIZE - len(res), res)
    responseLen = int.from_bytes(res[:MSGLEN_SIZE], byteorder='big') + MSGLEN_SIZE
    if len(res) < responseLen:
        res = _recvBytes(conn, responseLen - len(res), res)

    conn.shutdown(socket.SHUT_RD)
    print('true len', len(res))
    return res[MSGLEN_SIZE:]
def _recvBytes(conn, num, prevRecvd) -> bytes:
    '''receives excactly num bytes'''
    numRecvd = 0
    response = bytearray(prevRecvd)
    while numRecvd < num:
        recvd = conn.recv(min(2048, num-numRecvd))
        response += recvd
        numRecvd += len(recvd)
    return response
