"""
blockchain.py
-------------
Talks to the HoneyLedger smart contract deployed on the Ethereum Sepolia testnet.

Every important event (bottle verification, harvest verification, batch creation)
can be permanently recorded here. The off-chain JSON database still stores the
full data (for speed); this module just writes a tamper-evident fingerprint of
that event to the blockchain and returns the transaction hash.
"""

import os
import json
import hashlib
import logging
from web3 import Web3

logger = logging.getLogger(__name__)

# ---- Configuration (loaded from environment variables, see .env) ----
INFURA_URL = os.environ.get("INFURA_SEPOLIA_URL")          # e.g. https://sepolia.infura.io/v3/xxxx
PRIVATE_KEY = os.environ.get("HONEYCHAIN_PRIVATE_KEY")     # wallet private key (never commit this!)
CONTRACT_ADDRESS = os.environ.get("HONEYLEDGER_CONTRACT_ADDRESS")

CONTRACT_ABI = json.loads('''
[
    {"inputs":[{"internalType":"string","name":"_recordType","type":"string"},{"internalType":"string","name":"_dataHash","type":"string"}],"name":"addRecord","outputs":[],"stateMutability":"nonpayable","type":"function"},
    {"anonymous":false,"inputs":[{"indexed":true,"internalType":"uint256","name":"id","type":"uint256"},{"indexed":false,"internalType":"string","name":"recordType","type":"string"},{"indexed":false,"internalType":"string","name":"dataHash","type":"string"},{"indexed":false,"internalType":"uint256","name":"timestamp","type":"uint256"},{"indexed":false,"internalType":"address","name":"addedBy","type":"address"}],"name":"RecordAdded","type":"event"},
    {"inputs":[{"internalType":"uint256","name":"_id","type":"uint256"}],"name":"getRecord","outputs":[{"internalType":"string","name":"","type":"string"},{"internalType":"string","name":"","type":"string"},{"internalType":"uint256","name":"","type":"uint256"},{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"getTotalRecords","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"internalType":"uint256","name":"","type":"uint256"}],"name":"records","outputs":[{"internalType":"string","name":"recordType","type":"string"},{"internalType":"string","name":"dataHash","type":"string"},{"internalType":"uint256","name":"timestamp","type":"uint256"},{"internalType":"address","name":"addedBy","type":"address"}],"stateMutability":"view","type":"function"}
]
''')

_w3 = None
_contract = None
_account = None


def _init():
    """Lazily set up the Web3 connection so the app doesn't crash on import
    if the blockchain env vars aren't configured yet (e.g. during local dev)."""
    global _w3, _contract, _account
    if _w3 is not None:
        return
    if not (INFURA_URL and PRIVATE_KEY and CONTRACT_ADDRESS):
        raise RuntimeError(
            "Blockchain not configured. Set INFURA_SEPOLIA_URL, "
            "HONEYCHAIN_PRIVATE_KEY and HONEYLEDGER_CONTRACT_ADDRESS in your environment."
        )
    _w3 = Web3(Web3.HTTPProvider(INFURA_URL))
    _account = _w3.eth.account.from_key(PRIVATE_KEY)
    _contract = _w3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=CONTRACT_ABI)


def is_configured() -> bool:
    return bool(INFURA_URL and PRIVATE_KEY and CONTRACT_ADDRESS)


def hash_payload(data: dict) -> str:
    """Turn any event dict into a short, deterministic SHA-256 hash.
    We store the hash on-chain (cheap), not the raw data (expensive)."""
    encoded = json.dumps(data, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def add_record(record_type: str, data: dict) -> dict:
    """Write one event to the blockchain ledger.

    Returns a dict with the transaction hash, block explorer link, and the
    hash that was stored — or raises an exception if it fails (caller should
    catch this and fall back gracefully so a slow/unavailable testnet never
    breaks the demo).
    """
    _init()
    data_hash = hash_payload(data)

    tx = _contract.functions.addRecord(record_type, data_hash).build_transaction({
        "from": _account.address,
        "nonce": _w3.eth.get_transaction_count(_account.address),
        "gas": 200000,
        "gasPrice": _w3.eth.gas_price,
        "chainId": 11155111,  # Sepolia
    })
    signed = _w3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
    tx_hash = _w3.eth.send_raw_transaction(signed.raw_transaction)
    tx_hash_hex = tx_hash.hex()

    logger.info("Blockchain record added: type=%s tx=%s", record_type, tx_hash_hex)

    return {
        "tx_hash": tx_hash_hex,
        "data_hash": data_hash,
        "etherscan_url": f"https://sepolia.etherscan.io/tx/{tx_hash_hex}",
    }


def get_total_records() -> int:
    _init()
    return _contract.functions.getTotalRecords().call()


def get_record(record_id: int):
    _init()
    record_type, data_hash, timestamp, added_by = _contract.functions.getRecord(record_id).call()
    return {
        "id": record_id,
        "type": record_type,
        "data_hash": data_hash,
        "timestamp": timestamp,
        "added_by": added_by,
    }
