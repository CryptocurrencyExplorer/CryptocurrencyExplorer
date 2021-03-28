import decimal
import os
import sys
from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine, inspect
from sqlalchemy.sql import desc
from sqlalchemy.exc import OperationalError
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
# This is a placeholder to indicate the transaction is empty
EMPTY = ''
EXPECTED_TABLES = set(['addresses', 'address_summary', 'blocks', 'blocktxs', 'txs', 'txout', 'txin'])


def lets_boogy(the_blocks):
    if the_blocks[0] == 0:
        total_cumulative_difficulty = decimal.Decimal(0.0)
    else:
        total_cumulative_difficulty = db.session.query(Blocks).order_by(desc('cumulative_difficulty')).first().cumulative_difficulty

    for block_height in the_blocks:
        total_value_out = decimal.Decimal(0.0)
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
            try:
                raw_block_tx = cryptocurrency.getrawtransaction(this_transaction, 1)
                if len(the_block['tx']) != 1:
                    if number == 0:
                        print(cryptocurrency.getrawtransaction(this_transaction, 1))
                    else:
                        a = cryptocurrency.getrawtransaction(cryptocurrency.getrawtransaction(this_transaction, 1)['txid'], 1)
                        b = [cryptocurrency.getrawtransaction(x['txid'], 1) for x in a['vin']]
                        c = [f"{x['vout'][0]['scriptPubKey']['addresses'][0]} / {x['vout'][0]['value']}" for x in b]
                        print(c)
                        total_value_out += sum(x['vout'][0]['value'] for x in b)
                        print(total_value_out)
                else:
                    this_specific_transaction = cryptocurrency.getrawtransaction(this_transaction, 1)
                    total_value_out += this_specific_transaction['vout'][0]['value']
                    print(total_value_out)
                the_tx = TXs(txid=raw_block_tx['txid'],
                             version=raw_block_tx['version'],
                             locktime=raw_block_tx['locktime'])
                db.session.add(the_tx)
            except JSONRPCException as e:
                if 'No information available about transaction' in str(e):
                    # TODO - Add something to indicate this transaction is unavailable
                    the_tx = TXs(txid=this_transaction,
                                 version=0,
                                 locktime=0)
                    db.session.add(the_tx)
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
        total_cumulative_difficulty += decimal.Decimal(the_block['difficulty'])
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
                                      cumulative_difficulty=total_cumulative_difficulty,
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
                                      cumulative_difficulty=total_cumulative_difficulty,
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
                                      cumulative_difficulty=total_cumulative_difficulty,
                                      value_out=decimal.Decimal(1.0),
                                      transaction_fees=decimal.Decimal(1.0),
                                      total_out=decimal.Decimal(1.0))
        db.session.add(this_blocks_info)
        db.session.commit()
        print(f"committed block {block_height}")


def detect_flask_config():
    if app_key == rb"""app_key""":
        print("Go into config.py and change the app_key!")
        sys.exit()
    if csrf_key == "csrf_key":
        print("Go into config.py and change the csrf_key!")
        sys.exit()


def detect_coin(cryptocurrency):
    try:
        genesis_hash = cryptocurrency.getblockhash(0)
        coin = bootstrap.get(genesis_hash)
        if coin is not None:
            if coin_name is None:
                print(f"coin_name in config.py has been autodetected as the following: {coin}")
            return coin
        else:
            print("This isn't a coin I'm aware of.")
            sys.exit()
    except JSONRPCException as e:
        if '401 Authorization Required' in str(e):
            print("The rpcport is right but one or both these is wrong: rpcuser/rpcpassword.")
            print("Go into config.py and fix this.")
            sys.exit()


def detect_tables():
    try:
        engine = create_engine(database_uri)
        inspector = inspect(engine)
        detected_tables = set(inspector.get_table_names())
        engine.dispose()
        # TODO - The expected tables will change when segwit is supported.
        # Though, obviously segwit won't be manipulated/added to if the specific chain doesn't support it.
        extra_tables_detected = detected_tables.difference(EXPECTED_TABLES)
        valid_tables_missing = EXPECTED_TABLES.difference(detected_tables)
        if len(detected_tables) == 0:
            db.create_all()
        else:
            if len(extra_tables_detected) != 0:
                print('There were extra tables detected:')
                print(extra_tables_detected)
            elif len(valid_tables_missing) != 0:
                print('These expected tables are missing:')
                print(valid_tables_missing)
    except OperationalError as e:
        if 'password authentication failed' in str(e):
            print('Incorrect password for SQLAlchemy. Go into config.py and fix this.')
            sys.exit()


if __name__ == '__main__':
    db.drop_all()

    if autodetect_config:
        detect_flask_config()
    try:
        cryptocurrency = AuthServiceProxy(f"http://{rpcuser}:{rpcpassword}@127.0.0.1:{rpcport}")
    except(JSONRPCException, ValueError):
        print("One or all of these is wrong: rpcuser/rpcpassword/rpcport. Go into config.py and fix this.")
        sys.exit()

    if autodetect_coin:
        detect_coin(cryptocurrency)
    if autodetect_tables:
        detect_tables()

    most_recent_block = cryptocurrency.getblockcount()

    try:
        most_recent_stored_block = db.session.query(Blocks).order_by(desc('height')).first().height
    except AttributeError:
        the_blocks = range(0, most_recent_block + 1)
        lets_boogy(the_blocks)
    else:
        if most_recent_stored_block != most_recent_block:
            the_blocks = range(most_recent_stored_block + 1, most_recent_block + 1)
            lets_boogy(the_blocks)
        else:
            print("Looks like you're all up-to-date")
            sys.exit()