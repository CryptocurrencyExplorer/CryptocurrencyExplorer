import decimal
import sys
from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException
import click
from flask import Flask
from sqlalchemy import create_engine, inspect
from sqlalchemy.sql import desc
from sqlalchemy.exc import OperationalError
import blockchain
from blockchain import SUPPORTED_COINS
from config import autodetect_coin, autodetect_config, autodetect_rpc, autodetect_tables
from config import coin_name, rpcpassword, rpcport, rpcuser
from config import app_key, csrf_key, database_uri
from models import db
from models import Addresses, AddressSummary, Blocks, BlockTXs, CoinbaseTxIn
from models import TXs, LinkedTxOut, TxOut, LinkedTxOut, TXIn


# This is a placeholder to indicate the transaction is empty
EMPTY = ''
EXPECTED_TABLES = {'addresses', 'address_summary', 'blocks', 'blocktxs', 'coinbase_txin', 'txs', 'linked_txout',
                   'txout', 'linked_txin', 'txin'}

def create_app():
    first_run_app = Flask(__name__)
    first_run_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    first_run_app.config['SQLALCHEMY_DATABASE_URI'] = database_uri
    db.init_app(first_run_app)
    return first_run_app


def process_block(item):
    if item is not None:
        return f'Processing block {item} / {the_blocks[-1]}'


def lets_boogy(the_blocks):
    if the_blocks[0] == 0:
        total_cumulative_difficulty = decimal.Decimal(0.0)
    else:
        total_cumulative_difficulty = db.session.query(Blocks).order_by(
                                      desc('cumulative_difficulty')).first().cumulative_difficulty
        current_block = db.session.query(Blocks).order_by(desc('height')).first()
        if current_block.nexthash == 'PLACEHOLDER':
            next_block_hash = cryptocurrency.getblockhash(current_block.height + 1)
            current_block.nexthash = next_block_hash
            db.session.commit()

    with click.progressbar(the_blocks, item_show_func=process_block) as progress_bar:
        for block_height in progress_bar:
            total_value_out = decimal.Decimal(0.0)
            block_raw_hash = cryptocurrency.getblockhash(block_height)
            the_block = cryptocurrency.getblock(block_raw_hash)
            total_cumulative_difficulty += decimal.Decimal(the_block['difficulty'])
            raw_block_transactions = the_block['tx']
            how_many_transactions = len(raw_block_transactions)

            # Probably better to just take the latest block's height and subtract this block's height to get confirmations
            # block_confirmations = cryptocurrency.getblockcount() + 1 - block_height

            # If there's more than one transaction, we need to calculate fees.
            # Since this involves inputs - outputs, the coinbase is done last.
            for number, this_transaction in enumerate(raw_block_transactions):
                # "The tx_id column is the transaction to which this output belongs,
                # n is the position within the output list."
                # https://grisha.org/blog/2017/12/15/blockchain-and-postgres/
                this_tx = BlockTXs(block_height=block_height,
                                   n=number,
                                   tx_id=this_transaction)
                db.session.add(this_tx)
                try:
                    raw_block_tx = cryptocurrency.getrawtransaction(this_transaction, 1)
                except JSONRPCException as e:
                    pass
                    # if 'No information available about transaction' in str(e):
                    # TODO - Add something to indicate this transaction is unavailable
                else:
                    the_tx = TXs(txid=raw_block_tx['txid'],
                                 version=raw_block_tx['version'],
                                 locktime=raw_block_tx['locktime'])
                    db.session.add(the_tx)

                    how_many_vin = len(raw_block_tx['vin'])
                    how_many_vout = len(raw_block_tx['vout'])

                    for vout in raw_block_tx['vout']:
                        total_value_out += vout['value']
                        commit_transaction_out = TxOut(n=vout['n'],
                                                       value=vout['value'],
                                                       scriptpubkey='test',
                                                       address=vout['scriptPubKey']['addresses'][0])
                        db.session.add(commit_transaction_out)

                    for vin in raw_block_tx['vin']:
                        if number == 0:
                            commit_coinbase = CoinbaseTxIn(block_height=the_block['height'],
                                                           scriptsig=vin['coinbase'],
                                                           sequence=vin['sequence'])
                            db.session.add(commit_coinbase)
                        else:
                            commit_transaction_in = TXIn(tx_id=this_transaction,
                                                         n=number,
                                                         scriptsig='test',
                                                         sequence=0,
                                                         # TODO - This needs pulled from bootstrap
                                                         # TODO - Witness actually needs supported
                                                         witness=None)
                            db.session.add(commit_transaction_in)
                            # if 'vout' in vin and 'txid' in vin:
                                # If this transaction is referenced, this should never be invalid.
                                # Not sure if that's even possible.
                                # vin_transaction = cryptocurrency.getrawtransaction(vin['txid'], 1)
                                # print(f"{raw_block_tx['txid']} references {vin['txid']} as previous output -- position: {vin['vout']} of {vin_transaction['txid']}")
                                # commit_transaction_in = TXIn(tx_id=this_transaction,
                                                             # n=number,
                                                             # scriptsig='test',
                                                             # sequence=0,
                                                             # TODO - This needs pulled from bootstrap
                                                             # TODO - Witness actually needs supported
                                                             # witness=None)
            if block_height == 0:
                prev_block_hash = '0000000000000000000000000000000000000000000000000000000000000000'
                next_block_hash = the_block['nextblockhash']
            elif block_height != the_blocks[-1]:
                prev_block_hash = the_block['previousblockhash']
                next_block_hash = the_block['nextblockhash']
            elif block_height == the_blocks[-1]:
                prev_block_hash = the_block['previousblockhash']
                next_block_hash = 'PLACEHOLDER'
            this_blocks_info = Blocks(height=the_block['height'],
                                      hash=the_block['hash'],
                                      version=the_block['version'],
                                      prevhash=prev_block_hash,
                                      nexthash=next_block_hash,
                                      merkleroot=the_block['merkleroot'],
                                      time=the_block['time'],
                                      bits=the_block['bits'],
                                      nonce=the_block['nonce'],
                                      size=the_block['size'],
                                      difficulty=decimal.Decimal(the_block['difficulty']),
                                      cumulative_difficulty=total_cumulative_difficulty,
                                      value_out=total_value_out,
                                      transactions=how_many_transactions,
                                      # TODO
                                      transaction_fees=decimal.Decimal(1.0))
            db.session.add(this_blocks_info)
            db.session.commit()


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
    except JSONRPCException as e:
        if '401 Authorization Required' in str(e):
            print("The rpcport is right but one or both these is wrong: rpcuser/rpcpassword.")
            print("Go into config.py and fix this.")
        sys.exit()
    else:
        if coin_name.capitalize() not in SUPPORTED_COINS:
            coin_found = False
            for each in SUPPORTED_COINS:
                try:
                    the_coin = getattr(blockchain, each)()
                    if the_coin.unique['genesis']['hash'] == genesis_hash:
                        print(f'This coin was detected as: {each}')
                        print(f'Please put "{each}" into config.py under `coin_name`')
                        coin_found = True
                        break
                # TypeError needs caught in case someone tries non-strings for the coin_name... for whatever reason?
                except(AttributeError, TypeError):
                    pass
            if not coin_found:
                print("I wasn't able to auto-detect a coin/token.")
                print("You're either trying something not supported or haven't followed the README for the project.")
                sys.exit()
        else:
            coin_name_in_config = coin_name.capitalize()
            print(f"It looks like you already have `{coin_name_in_config}` set as the coin_name in config.py")
            print("Skipping auto-detection of coin because of this")

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
                sys.exit()
            elif len(valid_tables_missing) != 0:
                print('These expected tables are missing:')
                print(valid_tables_missing)
                sys.exit()
    except OperationalError as e:
        if 'password authentication failed' in str(e):
            print('Incorrect password for SQLAlchemy. Go into config.py and fix this.')
            sys.exit()


if __name__ == '__main__':
    first_run_app = create_app()
    first_run_app.app_context().push()

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
    except OperationalError as e:
        if 'database' in str(e) and 'does not exist' in str(e):
            print("You'll need to follow the documentation to create the database.")
            print("This isn't possible through Flask right now (issue \#15 in the Github repo).")
    else:
        while True:
            user_input = input('(C)ontinue, (D)rop all, or (E)xit?: ').lower()
            if user_input == 'd':
                db.drop_all()
                break
            elif user_input == 'c':
                break
            elif user_input == 'e':
                sys.exit()
        if most_recent_stored_block != most_recent_block:
            the_blocks = range(most_recent_stored_block + 1, most_recent_block + 1)
            lets_boogy(the_blocks)
        else:
            print("Looks like you're all up-to-date")
            sys.exit()
