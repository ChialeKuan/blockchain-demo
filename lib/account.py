import ecdsa
import json
from binascii import hexlify, unhexlify
from time import time
from lib.crypto import *


class Account:
    def __init__(self, name: str):
        self.name = name
        self.pr_dir = './data/' + self.name + '.key'
        self.pu_dir = './data/' + self.name + '.pub'

        # 生成私钥和公钥
        self.pr = ecdsa.SigningKey.generate(curve=ecdsa.SECP256k1)
        self.pu = self.pr.get_verifying_key()
        # 以 bytes 形式保存
        self.pr_s = self.pr.to_string().hex()
        self.pu_s = self.pu.to_string().hex()
        # 计算得到对应的地址
        self.address = get_address(self.pu_s)
        # 把私钥和公钥存到本地
        with open(self.pr_dir, 'w') as file:
            file.write(self.pr_s)
        with open(self.pu_dir, 'w') as file:
            file.write(self.pu_s)

    def show_info(self):
        print("private key:", self.pr_s)
        print("public key:", self.pu_s)
        print("address:", self.address)

    def get_pub_string(self):
        return self.pu_s

    def get_address(self):
        return self.address

    def sign(self, msg: str) -> str:
        '''
        使用账户的私钥进行签名
        :param msg: 要签名的消息
        :return: 签名
        '''
        signature = self.pr.sign(msg.encode('utf-8'))
        return signature.hex()

    def balance_n_records(self, utxo):
        '''
        根据 utxo 来计算用户的余额 和 当前为花费的 tx 的对应 hash 和 n 值的列表
        :param utxo:
        :return: 余额，未花费 tx 的索引
        '''
        total = 0
        records = []
        for tx_hash in utxo:
            for item in utxo[tx_hash]:
                if item['to'] == self.address:
                    total += item['value']
                    # (hash, n, value)
                    records.append((tx_hash, item['n'], item['value']))
        return total, records

    def show_balance(self, utxo):
        print("Balance:", self.balance_n_records(utxo)[0])

    def transfer(self, destin: str, amount: int, utxo: dict):
        '''
        转账的对外接口，只需要提供转账的收款方和金额，以及需要更新的utxo
        需要检查 转账金额是否为负（不允许贷款）以及是否有足够多的金额完成转账
        :param destin: 收款方
        :param amount: 金额
        :param utxo:
        :return: None / 待广播的 tx 列表
        '''
        if amount <= 0:
            return None
        total, records = self.balance_n_records(utxo)
        if total < amount:
            print("Only remaining:", total)
            return None
        pay = 0
        sources = []
        i = 0
        while pay < amount:
            pay += records[i][2]
            sources.append((records[i][0], records[i][1]))
            i += 1
        if pay == amount:
            destins = [(destin, amount)]
        else:
            destins = [(destin, amount), (self.address, pay - amount)]
        return self.new_transaction(sources, destins)

    def new_transaction(self, sources: list, destins: list):
        '''
        transfer 所调用的内部接口，构造生成一个 tx 记录
        考虑到合并支付和找零，in 和 out 字段都可能有多个记录
        :param sources: [(source_hash, source_index)..]
        :param destins: [(destin_recp, destin_value)..'
        :return: 待广播的 tx 列表
        '''
        tx_input = []
        tx_output = []

        for source in sources:
            prev_out = {
                "hash": source[0],
                "n": source[1],
            }
            record = {
                "prev_out": prev_out,
                "public_key": self.pu_s,
                "sig": self.sign(json.dumps(prev_out, sort_keys=True)),
            }
            tx_input.append(record)

        n = 0
        for destin in destins:
            record = {
                "n": n,
                "recipient": destin[0],
                "value": destin[1],
            }
            n += 1
            tx_output.append(record)

        timestamp = time()
        text = str(timestamp) + json.dumps(tx_input, sort_keys=True) + json.dumps(tx_output, sort_keys=True)
        tx = {
            "hash": double_sha256(text),
            "timestamp": timestamp,
            "in": tx_input,
            "out": tx_output
        }
        return tx
