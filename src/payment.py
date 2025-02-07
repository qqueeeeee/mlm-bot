from tronapi import HttpProvider
from tronapi import Tron

from src.config import PRIVATE_KEY, load_settings

full_node = HttpProvider('https://api.trongrid.io')
solidity_node = HttpProvider('https://api.trongrid.io')
event_server = HttpProvider('https://api.trongrid.io')
tron = Tron(full_node=full_node,
            solidity_node=solidity_node,
            event_server=event_server)

settings = load_settings()
tron.private_key = PRIVATE_KEY
tron.default_address = settings['wallet']


def set_default_address(address):
    tron.default_address = address


def set_key(key):
    tron.private_key = key


def is_wallet_valid(wallet: str) -> bool:
    return bool(tron.isAddress(wallet))


def verify_transaction(txid: str, user_wallet: str, wallet: str) -> int:
    try:
        result = tron.trx.get_transaction(txid)
        val = result['raw_data']['contract'][0]['parameter']['value']
        to_address = tron.address.from_hex(val['to_address'])
        from_address = tron.address.from_hex(val['owner_address'])
        amount = tron.fromSun(val['amount'])
        if to_address.decode('ascii') != wallet:
            return False, 'This transaction was not made to our wallet.'
        elif from_address.decode('ascii') != user_wallet:
            return False, 'This transaction was not received from your wallet.'
        else:
            return True, amount
    except ValueError as e:
        return False, str(e)
    except Exception as e:
        return False, str(e)


def pay(to: str, amount: float) -> bool:
    fee = 0.26
    amount = amount - fee
    try:
        res = tron.trx.send_transaction(to, float(amount))
        if res.get('result'):
            return True, res['txid']
        else:
            print(f"Payment error: {res}")
            return False, 'Transaction failed.'
    except Exception as e:
        print(f"Payment exception: {e}")
        return False, str(e)