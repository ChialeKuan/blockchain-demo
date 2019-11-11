import ecdsa
import base58
from Crypto.Hash import RIPEMD, SHA256
from math import ceil


def double_sha256(text: str) -> str:
    '''
    验证时常用的 double SHA256 散列
    :param text: 待验证字符串
    :return: 散列值
    '''
    h = SHA256.new()
    h.update(text.encode('utf-8'))
    checksum = h.hexdigest()
    h = SHA256.new()
    h.update(checksum.encode('utf-8'))
    checksum = h.hexdigest()
    return checksum


def get_address(public_key: str) -> str:
    '''
    通过公钥计算得到交易的地址
    :param public_key: 公钥，以字符串的形式传输，对应 Account.pu_s
    :return: 交易的地址
    '''
    # SHA256
    h = SHA256.new()
    h.update(public_key[2:].encode('utf-8'))
    address = h.hexdigest()

    # RIPEMD
    h = RIPEMD.new()
    h.update(address.encode('utf-8'))
    address = h.hexdigest()
    address = '00' + address

    # Double SHA256
    checksum = double_sha256(address)[:8]

    # base58
    address = address + checksum
    address = base58.b58encode_int(int(address, 16))
    return address.decode('utf-8')


def get_merkle_tree_root(txs: list) -> str:
    '''
    通过 区块 的 tx 字段来计算 merkle 树根结点的值
    :param txs: 区块的 tx 字段
    :return: 返回根结点的值
    '''
    if len(txs) == 0:
        return ""
    if len(txs) == 1:
        return double_sha256(txs[0]['hash'])

    # 计算第0层的hash值
    temp = []
    for tx in txs:
        temp.append(tx['hash'])
    # 深复制
    txs = list(temp)
    temp.clear()
    # 向上逐渐计算
    while len(txs) != 1:
        for i in range(0, len(txs) - 1, 2):
            temp.append(double_sha256(txs[i] + txs[i + 1]))
        if len(txs) % 2 == 1:
            temp.append(double_sha256(txs[-1]))
        txs = list(temp)
        temp.clear()
    return txs[0]


def get_tree_neighbor_indexes(index: int, size: int) -> list:
    assert index < size
    if size == 0:
        return []
    if size == 1:
        return []
    res = []
    i = 0
    while size != 1:
        if index % 2 == 1:
            res.append((i, index - 1))
        else:
            res.append((i, index + 1))
        index = index // 2
        size = ceil(size / 2)
        i = i + 1
    return res


def verify_sig(msg: str, signature: str, pu_s: str) -> bool:
    '''
    验证签名，消息，签名和公钥都以字符串的形式提供
    :param msg: 消息
    :param signature: 签名
    :param pu_s: 公钥
    :return: 是否验证成功
    '''
    pu_b = bytes.fromhex(pu_s)
    pu = ecdsa.VerifyingKey.from_string(pu_b, curve=ecdsa.SECP256k1)
    signature = bytes.fromhex(signature)
    return pu.verify(signature, msg.encode('utf-8'))
