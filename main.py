from threading import Thread
from lib.network import *
from lib.account import *
from lib.chain import *

print('Working on', HOST, ":", PORT)

BC = BlockChain()
CURRENT = None


class ListenThread(Thread):
    # 负责处理收到的报文
    def __init__(self, thread_num=0, timeout=1.0):
        super(ListenThread, self).__init__()
        self.thread_num = thread_num
        self.stopped = False
        self.timeout = timeout

    def run(self):
        def receive():
            while True:
                # time.sleep(1)
                try:
                    buffer, address = SOCKET.recvfrom(BUF_SIZE)
                except ConnectionResetError:
                    continue

                buffer = buffer.decode('utf-8')
                if buffer == '':
                    continue
                msg = json.loads(buffer)

                content = msg['content']
                if msg['type'] == 'broadcast_tx':
                    BC.receive_tx(content)
                elif msg['type'] == 'broadcast_block':
                    # check the index
                    if msg['index'] == len(BC.chain):
                        # got a chance to be verified and accepted
                        BC.receive_block(content)
                    elif msg['index'] < len(BC.chain):
                        # warn that the other chain is too short
                        response_chain(address, msg['index'])
                    elif msg['index'] > len(BC.chain):
                        # we need to request a new chain
                        request_chain()
                elif msg['type'] == 'request_chain':
                    response_chain(address, content)
                elif msg['type'] == 'response_chain':
                    BC.resolve_conflicts(content)

        sub_thread = Thread(target=receive, args=())
        sub_thread.setDaemon(True)
        sub_thread.start()
        while not self.stopped:
            sub_thread.join(self.timeout)

    def stop(self):
        self.stopped = True

    def is_stopped(self):
        return self.stopped


def request_chain():
    msg = {"type": "request_chain",
           "content": len(BC.chain),
           }
    broadcast(json.dumps(msg, sort_keys=True))


def response_chain(address, chain_len):
    if len(BC.chain) <= chain_len:
        return
    msg = {"type": "response_chain",
           "content": BC.chain,
           }
    send_msg(json.dumps(msg, sort_keys=True), address)


def transaction():
    if CURRENT is None:
        print("No account available")
        return
    destin = input("input the payee's address:")
    amount = input("input the amount:")
    new_tx = CURRENT.transfer(destin, int(amount), BC.utxo)
    if new_tx is None:
        print("transaction failed")
        return
    # update current txs
    BC.current_transactions.append(new_tx)
    # update utxo
    # BC.update_utxo([new_tx])
    msg = {"type": "broadcast_tx",
           "content": new_tx,
           }
    broadcast(json.dumps(msg, sort_keys=True))


def account():
    global CURRENT
    account_help_info = '1 View Current Account\n' \
                        '2 View Balance\n' \
                        '3 Create New Account'

    while True:
        print(account_help_info)
        opt = input('>')
        if opt == '1':
            if CURRENT is not None:
                CURRENT.show_info()
                break
            else:
                print("No account now")
        elif opt == '2':
            if CURRENT is not None:
                CURRENT.show_balance(BC.utxo)
                break
            else:
                print("No account now")
        elif opt == '3':
            name = input("Input your account name:")
            CURRENT = Account(name)
            CURRENT.show_info()
            break
        else:
            print("Out of Range")


def mine():
    '''
    实际上就是产生新块的过程
    挖矿的时候需要提供矿工的账号
    :return: None
    '''
    if CURRENT is None:
        print("No account available")
        return
    new_block = BC.new_block(CURRENT)
    if new_block is None:
        print("mining failed")
        return
    # 广播消息
    msg = {"type": "broadcast_block",
           "index": len(BC.chain) - 1,
           "content": new_block,
           }
    broadcast(json.dumps(msg, sort_keys=True))
    # 显示挖矿后的余额
    CURRENT.show_balance(BC.utxo)


def debug():
    debug_help_info = '1 View Chain\n' \
                      '2 View UTXO\n' \
                      '3 View Current Transactions\n' \
                      '4 Validate Current Chain\n' \
                      '5 Exit Debug'
    while True:
        print(debug_help_info)
        opt = input('>')
        if opt == '1':
            BC.show_chain()
        elif opt == '2':
            BC.show_utxo()
        elif opt == '3':
            BC.show_tx()
        elif opt == '4':
            print(BC.valid_chain(BC.chain))
        elif opt == '5':
            break
        else:
            print("Out of Range")


thread = ListenThread()
thread.start()

help_info = '1 Account\t2 Mine\t3 Transfer\t4 Node\t5 Update\t' \
            'D Debug\tE Exit'

while True:
    print(help_info)
    s = input('>')
    if s == '1':
        account()
    elif s == '2':
        mine()
    elif s == '3':
        transaction()
    elif s == '4':
        nodes()
    elif s == '5':
        request_chain()
    elif s == 'D':
        debug()
        continue
    elif s == 'E':
        break
    else:
        continue
    # broadcast(s)

thread.stop()
thread.join()
SOCKET.close()
