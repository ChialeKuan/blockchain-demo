import hashlib
import json
from time import time
from lib.crypto import *
from lib.account import *


class BlockChain:
    def __init__(self):
        self.current_transactions = []
        self.chain = []
        # a dict, could be indexed faster
        self.utxo = {}

    @staticmethod
    def valid_proof(header: dict) -> bool:
        '''
        挖矿的比特数为4
        :param header: 即区块的header字段
        :return: 是否满足工作量要求
        '''
        guess = f'{header["timestamp"]}{header["hash_prev_block"]}' \
            f'{header["hash_merkle_root"]}{header["nonce"]}'
        guess_hash = double_sha256(guess)
        return guess_hash[:4] == "0000"

    def new_block(self, account: Account):
        '''
        即为挖矿的过程，需要提供矿工的账号来记录报酬
        :param account: 矿工的账号
        :return:
        '''
        # 需要提供账号
        if account is None:
            print('No Account to do the mining')
            return None
        # 计算上一个节点的hash值
        if len(self.chain) == 0:
            hash_prev_block = 0
        else:
            hash_prev_block = double_sha256(json.dumps(self.chain[-1], sort_keys=True))
        # 当前需要记录的 tx
        txs = self.current_transactions
        # 报酬，20元
        sources = []
        destins = [(account.get_address(), 20)]
        reward = account.new_transaction(sources, destins)
        txs.insert(0, reward)
        # 构造初步的header（还需要计算nonce）
        header = {
            'timestamp': time(),
            'hash_prev_block': hash_prev_block,
            'hash_merkle_root': get_merkle_tree_root(txs),
            'nonce': 0,
        }
        # 挖矿的过程
        proof = 0
        while self.valid_proof(header) is False:
            proof = proof + 1
            header['nonce'] = proof
        block = {
            'header': header,
            'tx': txs,
        }
        self.update_utxo(txs)
        # Reset the current list of transactions
        self.current_transactions = []
        self.chain.append(block)
        return block

    def receive_block(self, block: dict):
        '''
        收到其他节点的块，需要进行验证
        然后更新本地相关的数据，如utxo和当前的tx
        :param block: 收到的块，
        :return: None
        '''
        if self.valid_proof(block['header']) is False:
            print("receive a false block")
            return None
        if len(self.chain) != 0:
            if block['header']['hash_prev_block'] != double_sha256(json.dumps(self.chain[-1], sort_keys=True)):
                print("receive an unmatch block")
                return None
        self.update_utxo(block['tx'])
        # current_transaction -= block['tx']
        for tx in block['tx']:
            for ty in self.current_transactions:
                if tx['hash'] == ty['hash']:
                    self.current_transactions.remove(ty)

        self.chain.append(block)

    def show_chain(self):
        print(json.dumps(self.chain, indent=2, sort_keys=True))

    def valid_chain(self, chain: list) -> bool:
        '''
        验证给定的链是否是有效的，从以下几个方面验证
        1 每一个块的 hash_prev_block 是否和上一个块的散列值相符
        2 每一个块的 hash_merkle_root 是否和当前的 tx 符合
        3 符合工作量证明
        :param chain: 带验证的链
        :return: 是否有效
        '''
        current_index = 1
        while current_index < len(chain):
            header = chain[current_index]['header']
            tx = chain[current_index]['tx']
            # check header hash
            hash_prev_block = double_sha256(json.dumps(chain[current_index - 1], sort_keys=True))
            if header['hash_prev_block'] != hash_prev_block:
                print('previous block unmatch')
                return False
            # check merkle root
            hash_merkle_root = get_merkle_tree_root(tx)
            if header['hash_merkle_root'] != hash_merkle_root:
                print('merkle root unmatch')
                return False
            # proof of work
            if self.valid_proof(header) is False:
                print('valid proof unmatch')
                return False
            current_index += 1
        return True

    def resolve_conflicts(self, new_chain: list):
        '''
        根据收到的 new_chain 对本地的链和utxo进行更新
        如果遇到以下情况则不更新
        1 新的链较短
        2 新的链的创始区块和本地的不一致
        :param new_chain:
        :return:
        '''
        if len(new_chain) <= len(self.chain):
            return
        if self.valid_chain(new_chain) is False:
            print("false chain")
            return
        if len(self.chain) != 0 and self.chain[0] != new_chain[0]:
            print("Not a valid chain source")
            return
        self.chain = new_chain
        self.utxo = {}
        for block in self.chain:
            self.update_utxo(block['tx'])

    def update_utxo(self, tx_list: list):
        '''
        每收到一个新的块，则对utxo进行更新（包括自己挖矿和收到其他节点的广播）
        把每个tx中消费的记录删除，并且把out中的记录添加到utxo里面
        :param tx_list: 块的 tx 字段
        :return: None
        '''
        if self.valid_tx_list(tx_list) is False:
            print("UTXO: valid tx list failed")
            return
        for tx in tx_list:
            if len(tx['in']) == 0:
                sign_address = 0
            else:
                sign_address = get_address(tx['in'][0]['public_key'])
            # 把已经支付的从utxo中删除
            for source in tx['in']:
                self.remove_utxo(source['prev_out']['hash'], source['prev_out']['n'])
            # 把未花费的添加到utxo里，这里根据n的数量，应该是一个列表
            self.utxo[tx['hash']] = []
            n = 0
            for destin in tx['out']:
                record = {
                    'n': n,
                    'from': sign_address,
                    'to': destin['recipient'],
                    'value': destin['value'],
                }
                n += 1
                self.utxo[tx['hash']].append(record)

    def remove_utxo(self, hash: str, n: int):
        '''
        utxo根据tx的hash以及n值来唯一确定
        给定以上两个参数，可以确定删除的对象
        :param hash: tx 的 hash 值
        :param n: tx 的 n 值
        :return: None
        '''
        if hash not in self.utxo:
            return
        for item in self.utxo[hash]:
            if item['n'] == n:
                self.utxo[hash].remove(item)
                # 整个 hash 值对应的 tx 都已经使用完了
                if self.utxo[hash] == []:
                    self.utxo.pop(hash)

    def show_utxo(self):
        print(json.dumps(self.utxo, indent=2, sort_keys=True))

    def receive_tx(self, tx: dict):
        if tx is None:
            return
        self.current_transactions.append(tx)

    def show_tx(self):
        print(json.dumps(self.current_transactions, indent=2, sort_keys=True))

    def valid_tx_list(self, tx_list: list) -> bool:
        '''
        对区块的 tx 字段进行校验
        对第一个tx，需要满足 完整性的验证 和 挖矿酬劳不超过20
        对其他的tx，需要满足 完整性的验证，in 字段签名能够通过验证，签名和来源一致，总的 in 的金额不少于 out 的金额
        :param tx_list: 区块的 tx 字段
        :return: 是否满足要求
        '''
        if len(tx_list) == 0:
            return True
        # check the first tx
        checksum = tx_list[0]['hash']
        timestamp = tx_list[0]['timestamp']
        tx_input = tx_list[0]['in']
        tx_output = tx_list[0]['out']
        if tx_output[0]['value'] > 20:
            print('too much reward')
            return False
        text = str(timestamp) + json.dumps(tx_input, sort_keys=True) + json.dumps(tx_output, sort_keys=True)
        if checksum != double_sha256(text):
            print('tx checksum failed')
            return False
        # check following
        for i in range(1, len(tx_list)):
            checksum = tx_list[i]['hash']
            timestamp = tx_list[i]['timestamp']
            tx_input = tx_list[i]['in']
            tx_output = tx_list[i]['out']
            input_sum = 0
            output_sum = 0
            text = str(timestamp) + json.dumps(tx_input, sort_keys=True) + json.dumps(tx_output, sort_keys=True)
            if checksum != double_sha256(text):
                print('tx checksum failed')
                return False
            for j in tx_input:
                prev_out = j['prev_out']
                text = json.dumps(prev_out, sort_keys=True)
                input_sum += self.get_out_value(prev_out['hash'], prev_out['n'])
                # 是否拥有这笔钱
                if get_address(j['public_key']) != self.get_out_recipient(prev_out['hash'], prev_out['n']):
                    print("recipient unmatch")
                    return False
                # 验证签名
                if verify_sig(msg=text, signature=j['sig'], pu_s=j['public_key']) is False:
                    print('sig verification failed')
                    return False
            for j in tx_output:
                output_sum += j['value']
            # 验证数量
            if input_sum < output_sum:
                print('input cannot cover output')
                return False
        return True

    def get_out_value(self, hash: str, n: int):
        '''
        查询某笔 out 交易的额度是多少
        :param hash:
        :param n:
        :return:
        '''
        for block in self.chain:
            for tx in block['tx']:
                if tx['hash'] == hash:
                    for out in tx['out']:
                        if out['n'] == n:
                            return out['value']
        return 0

    def get_out_recipient(self, hash: str, n: int):
        '''
        查询某笔 out 交易的额度是多少
        :param hash:
        :param n:
        :return:
        '''
        for block in self.chain:
            for tx in block['tx']:
                if tx['hash'] == hash:
                    for out in tx['out']:
                        if out['n'] == n:
                            return out['recipient']
        return 0
