import decimal
import os
import sys
from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine, inspect
from sqlalchemy.sql import desc
from app import db
from blockchain import bootstrap
from config import autodetect_coin, autodetect_config, autodetect_rpc, autodetect_tables
from config import coin_name, rpcpassword, rpcport, rpcuser
from config import app_key, csrf_key, database_uri
from models import Addresses, AddressSummary, Blocks, BlockTXs, TXs, TxOut, TXIn

first_run_app = Flask(__name__)
first_run_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
first_run_app.config['SQLALCHEMY_DATABASE_URI'] = database_uri
database = SQLAlchemy(first_run_app)


def lets_boogy(the_blocks):
    for block_height in the_blocks:
        block_raw_hash = cryptocurrency.getblockhash(block_height)
        the_block = cryptocurrency.getblock(block_raw_hash)

        #block_confirmations = the_block['confirmations']
        # This is better to call in a Flask FOR loop, since it'll always be right.
        # Rather than storing it in a database, the FOR loop will take care of it.
        block_confirmations = cryptocurrency.getblockcount() + 1 - block_height

        block_transactions = the_block['tx']
        for number, this_transaction in enumerate(block_transactions):
            # "The tx_id column is the transaction to which this output belongs,
            # n is the position within the output list."
            # https://grisha.org/blog/2017/12/15/blockchain-and-postgres/
            this_tx = BlockTXs(block_height=block_height,
                               n=number,
                               tx_id=this_transaction)
            db.session.add(this_tx)
            if block_height == 0:
                this_transaction = {}
                the_TX = TXs(txid='d508b7916ec00595c1f8e1c767dc3b37392a5e68adf98118bca80a2ed58331d6',
                             version=1,
                             locktime=0)
                db.session.add(the_TX)
            else:
                raw_block_tx = cryptocurrency.getrawtransaction(this_transaction, 1)
                if len(the_block['tx']) != 1:
                    if number == 0:
                        print(cryptocurrency.getrawtransaction(this_transaction, 1))
                    else:
                        a = cryptocurrency.getrawtransaction(cryptocurrency.getrawtransaction(this_transaction, 1)['txid'], 1)
                        b = [cryptocurrency.getrawtransaction(x['txid'], 1) for x in a['vin']]
                        c = [f"{x['vout'][0]['scriptPubKey']['addresses'][0]} / {x['vout'][0]['value']}" for x in b]
                else:
                    print(raw_block_tx)

                the_TX = TXs(txid=raw_block_tx['txid'],
                             version=raw_block_tx['version'],
                             locktime=raw_block_tx['locktime'])
                db.session.add(the_TX)
            commit_transaction_in = TXIn(n=0,
                                         prevout_hash='test',
                                         prevout_n=0,
                                         scriptsig='test',
                                         sequence=0,
                                         witness='test',
                                         prevout_tx_id='test')
            commit_transaction_out = TxOut(tx_id='test',
                                           n=0,
                                           value=1.0,
                                           scriptpubkey='test',
                                           spent=False)
        # block_height == 0
        if block_height == 0:
            this_blocks_info = Blocks(height=the_block['height'],
                                      hash=the_block['hash'],
                                      version=the_block['version'],
                                      prevhash='0000000000000000000000000000000000000000000000000000000000000000',
                                      nexthash=the_block['nextblockhash'],
                                      merkleroot=the_block['merkleroot'],
                                      time=the_block['time'],
                                      bits=the_block['bits'],
                                      nonce=the_block['nonce'],
                                      size=the_block['size'],
                                      difficulty=decimal.Decimal(the_block['difficulty']),
                                      cumulative_difficulty=decimal.Decimal(1.0),
                                      value_out=decimal.Decimal(1.0),
                                      transaction_fees=decimal.Decimal(1.0),
                                      total_out=decimal.Decimal(1.0))
        # block_height is not the most recent
        elif block_height != the_blocks[-1]:
            this_blocks_info = Blocks(height=the_block['height'],
                                      hash=the_block['hash'],
                                      version=the_block['version'],
                                      prevhash=the_block['previousblockhash'],
                                      nexthash=the_block['nextblockhash'],
                                      merkleroot=the_block['merkleroot'],
                                      time=the_block['time'],
                                      bits=the_block['bits'],
                                      nonce=the_block['nonce'],
                                      size=the_block['size'],
                                      difficulty=decimal.Decimal(the_block['difficulty']),
                                      cumulative_difficulty=decimal.Decimal(1.0),
                                      value_out=decimal.Decimal(1.0),
                                      transaction_fees=decimal.Decimal(1.0),
                                      total_out=decimal.Decimal(1.0))
        # block_height IS the most recent
        else:
            this_blocks_info = Blocks(height=the_block['height'],
                                      hash=the_block['hash'],
                                      version=the_block['version'],
                                      prevhash=the_block['previousblockhash'],
                                      nexthash='PLACEHOLDER',
                                      merkleroot=the_block['merkleroot'],
                                      time=the_block['time'],
                                      bits=the_block['bits'],
                                      nonce=the_block['nonce'],
                                      size=the_block['size'],
                                      difficulty=decimal.Decimal(the_block['difficulty']),
                                      cumulative_difficulty=decimal.Decimal(1.0),
                                      value_out=decimal.Decimal(1.0),
                                      transaction_fees=decimal.Decimal(1.0),
                                      total_out=decimal.Decimal(1.0))
        db.session.add(this_blocks_info)
        db.session.commit()
        print(f"committed block {block_height}")


def detect_rpc():
    found_coins = {}
    for coin in bootstrap.values():
        coin = coin.lower()
        # rpc folder found
        if os.path.isdir(os.path.expanduser(f'~/.{coin}')):
            found_coins[coin] = True
    how_many_coins = len(found_coins)
    # If only one is found, good chance this is what the user wants to use
    if how_many_coins == 1:
        # If only one folder is found, check if a config file exists in it
        if os.path.isfile(os.path.expanduser(f'~/.{coin}/{coin}.conf')):
            # If the config file is found, open it and extract rpcuser/rpcpassword/rpcport
            with open(os.path.expanduser(f'~/.{coin}/{coin}.conf'), 'r') as rpc_file:
                full_rpc_file = rpc_file.readlines()
            for line in full_rpc_file:
                if line.strip() in ['rpcuser', 'rpcpassword', 'rpcport']:

    # No folders were found automatically, or more than one was found
    # User intervention is required, because we can't tell what they want
    else:



def detect_config():
    for each in [rpcuser, rpcpassword, rpcport]:
        if each is None:
            print("Go into config.py and change the rpc information so it's valid and not None")
            sys.exit()
    if app_key == rb"""app_key""":
        print("Go into config.py and change the app_key!")
        sys.exit()
    if csrf_key == "csrf_key":
        print("Go into config.py and change the csrf_key!")
        sys.exit()


def detect_coin(cryptocurrency):
    genesis_hash = cryptocurrency.getblockhash(0)
    coin = bootstrap.get(genesis_hash)
    if coin is not None:
        return coin
    else:
        print("This isn't a coin I'm aware of.")
        sys.exit()


def detect_tables():
    engine = create_engine(database_uri)
    inspector = inspect(engine)
    detected_tables = inspector.get_table_names()
    engine.dispose()
    if detected_tables != ['addresses', 'address_summary', 'blocks', 'blocktxs', 'txs', 'txout', 'txin']:
        return False
    else:
        return True


if __name__ == '__main__':
    if autodetect_config:
        detect_config()
    try:
        cryptocurrency = AuthServiceProxy(f"http://{rpcuser}:{rpcpassword}@127.0.0.1:{rpcport}")
    except JSONRPCException:
        print("One of these is wrong: rpcuser/rpcpassword/rpcport. Go into config.py and fix this.")
        sys.exit()

    if autodetect_coin:
        detect_coin(cryptocurrency)
    if autodetect_tables:
        detect_tables()
    most_recent_block = cryptocurrency.getblockcount()
    most_recent_stored_block = db.session.query(Blocks).order_by(desc('height')).first()

    if most_recent_stored_block is None:
        the_blocks = range(0, most_recent_block + 1)
        lets_boogy(the_blocks)
    elif most_recent_stored_block != most_recent_block:
        the_blocks = range(most_recent_stored_block, most_recent_block + 1)
        lets_boogy(the_blocks)
    else:
        print("Looks like you're all up-to-date")
        sys.exit()