from socket import *

HOST = '127.0.0.1'
BUF_SIZE = 4096

PORT = input('Port:')
LOOP = (HOST, int(PORT))
# 默认的通信节点
NODES = [('127.0.0.1', 8000), ('127.0.0.1', 8001), ('127.0.0.1', 8002),
         ('127.0.0.1', 8003), ('127.0.0.1', 8004), ('127.0.0.1', 8005)]
if LOOP in NODES:
    NODES.remove(LOOP)

SOCKET = socket(AF_INET, SOCK_DGRAM)
SOCKET.bind(LOOP)


def send_msg(msg, address):
    try:
        SOCKET.sendto(msg.encode('utf-8'), address)
    except ConnectionResetError as e:
        print(e, address, " is not reachable")
        NODES.remove(address)


def broadcast(msg):
    for address in NODES:
        send_msg(msg, address)


def nodes():
    global NODES
    nodes_help_info = '1 View Current Nodes\n' \
                      '2 Add New Nodes\n' \
                      '3 Remove Nodes'
    print(nodes_help_info)
    while True:
        opt = input('>')
        if opt == '1':
            for addr in NODES:
                print(addr)
            return
        elif opt == '2':
            print("Adding broadcasting nodes")
            addr = input('Input address:')
            port = input('Input port:')
            new_node = (addr, port)
            if new_node in NODES:
                print(new_node, 'was in the nodes list before')
                return
            NODES.append(new_node)
            print(new_node, 'is in the nodes list now')
            return
        elif opt == '3':
            print("Removing broadcasting nodes")
            addr = input('Input address:')
            port = input('Input port:')
            new_node = (addr, port)
            if new_node in NODES:
                print(new_node, 'was removed from the nodes list')
                NODES.remove(new_node)
                return
            print(new_node, 'was not in the nodes list')
            return
        else:
            print("Out of Range")
