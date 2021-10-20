import decimal
import logging
import sys
import click
from logging.handlers import RotatingFileHandler
from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException
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
from models import Addresses, AddressSummary, Blocks, TXIn, TXs, TxOut

# This is a placeholder to indicate the transaction is empty
EMPTY = ''
EXPECTED_TABLES = {'addresses', 'address_summary', 'blocks', 'txs', 'txout', 'txin'}


def create_app():
    first_run = Flask(__name__)
    # setup RotatingFileHandler with maxBytes set to 25MB
    rotating_log = RotatingFileHandler('explorer_first_run.log', maxBytes=25000000, backupCount=6)
    first_run.logger.addHandler(rotating_log)
    rotating_log.setFormatter(logging.Formatter(fmt='[%(asctime)s] / %(levelname)s in %(module)s: %(message)s'))
    first_run.logger.setLevel(logging.INFO)
    first_run.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    first_run.config['SQLALCHEMY_DATABASE_URI'] = database_uri
    db.init_app(first_run)
    return first_run


def process_block(item):
    if item is not None:
        return f'Processing block {item} / {the_blocks[-1]}'


def lets_boogy(the_blocks, uniques):
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
                try:
                    raw_block_tx = cryptocurrency.getrawtransaction(this_transaction, 1)
                except JSONRPCException as e:
                    pass
                    # if 'No information available about transaction' in str(e):
                    # TODO - Add something to indicate this transaction is unavailable
                else:
                    the_tx = TXs(txid=this_transaction,
                                 block_height=block_height,
                                 n=number,
                                 version=raw_block_tx['version'],
                                 locktime=raw_block_tx['locktime'])
                    db.session.add(the_tx)

                    how_many_vin = len(raw_block_tx['vin'])
                    how_many_vout = len(raw_block_tx['vout'])

                    for vout in raw_block_tx['vout']:
                        total_value_out += vout['value']
                        commit_transaction_out = TxOut(txid=this_transaction,
                                                       n=vout['n'],
                                                       value=vout['value'],
                                                       scriptpubkey=vout['scriptPubKey']['asm'],
                                                       address=vout['scriptPubKey']['addresses'][0],
                                                       linked_txid=None,
                                                       spent=False)
                        db.session.add(commit_transaction_out)

                    for vin in raw_block_tx['vin']:
                        if number == 0:
                            commit_coinbase = TXIn(block_height=block_height,
                                                   txid=this_transaction,
                                                   n=number,
                                                   scriptsig=vin['scriptSig']['asm'],
                                                   sequence=vin['sequence'],
                                                   # TODO - This needs pulled from bootstrap
                                                   # TODO - Witness actually needs supported
                                                   witness=None,
                                                   coinbase=True,
                                                   spent=False,
                                                   prevout_hash='test',
                                                   prevout_n=0)
                            db.session.add(commit_coinbase)
                        else:
                            commit_transaction_in = TXIn(block_height=block_height,
                                                         txid=this_transaction,
                                                         n=number,
                                                         scriptsig=vin['scriptSig']['asm'],
                                                         sequence=vin['sequence'],
                                                         # TODO - This needs pulled from bootstrap
                                                         # TODO - Witness actually needs supported
                                                         witness=None,
                                                         coinbase=False,
                                                         spent=False,
                                                         prevout_hash='test',
                                                         prevout_n=0)
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
                prev_block_hash = uniques['genesis']['prev_hash']
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
        first_run_app.logger.error("Go into config.py and change the app_key!")
        sys.exit()
    if csrf_key == "csrf_key":
        first_run_app.logger.error("Go into config.py and change the csrf_key!")
        sys.exit()


def detect_coin(cryptocurrency):
    try:
        genesis_hash = cryptocurrency.getblockhash(0)
    except JSONRPCException as e:
        if '401 Authorization Required' in str(e):
            first_run_app.logger.error("The rpcport is right but one or both these is wrong: rpcuser/rpcpassword.")
            first_run_app.logger.error("Go into config.py and fix this.")
        sys.exit()
    else:
        if coin_name.capitalize() not in SUPPORTED_COINS:
            for each in SUPPORTED_COINS:
                try:
                    the_coin = getattr(blockchain, each)()
                # TypeError needs caught in case someone tries non-strings for the coin_name... for whatever reason?
                except(AttributeError, TypeError):
                    pass
                else:
                    if the_coin.unique['genesis']['hash'] == genesis_hash:
                        first_run_app.logger.info(f'This coin was detected as: {each}')
                        first_run_app.logger.info(f'Please put "{each}" into config.py under `coin_name`')
                        return the_coin.unique
            # No reason to put an else above,
            # since this'll catch if nothing can be detected in the for loop
            first_run_app.logger.error("I wasn't able to auto-detect a coin/token.")
            first_run_app.logger.error("Are you using an unsupported coin/token?")
            first_run_app.logger.error("No? Then check out the README:")
            first_run_app.logger.error("https://github.com/CryptocurrencyExplorer/CryptocurrencyExplorer")
            sys.exit()
        else:
            coin_name_in_config = coin_name.capitalize()
            first_run_app.logger.info(f"You already have `{coin_name_in_config}` set as the coin_name in config.py")
            first_run_app.logger.info("Skipping auto-detection of coin because of this")
            the_coin = getattr(blockchain, coin_name_in_config)()
            return the_coin.unique


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
                first_run_app.logger.error('There were extra tables detected:')
                first_run_app.logger.error(extra_tables_detected)
                sys.exit()
            elif len(valid_tables_missing) != 0:
                first_run_app.logger.error('These expected tables are missing:')
                first_run_app.logger.error(valid_tables_missing)
                sys.exit()
    except OperationalError as e:
        if 'password authentication failed' in str(e):
            first_run_app.logger.error('Incorrect password for SQLAlchemy. Go into config.py and fix this.')
            sys.exit()


if __name__ == '__main__':
    first_run_app = create_app()
    first_run_app.app_context().push()

    if autodetect_config:
        detect_flask_config()
    try:
        cryptocurrency = AuthServiceProxy(f"http://{rpcuser}:{rpcpassword}@127.0.0.1:{rpcport}")
    except(JSONRPCException, ValueError):
        first_run_app.logger.error("One or all of these is wrong: rpcuser/rpcpassword/rpcport. Fix this in config.py")
        sys.exit()

    if autodetect_coin:
        uniques = detect_coin(cryptocurrency)
    if autodetect_tables:
        detect_tables()

    most_recent_block = cryptocurrency.getblockcount()

    try:
        most_recent_stored_block = db.session.query(Blocks).order_by(desc('height')).first().height
    except AttributeError:
        the_blocks = range(0, most_recent_block + 1)
        lets_boogy(the_blocks, uniques)
    except OperationalError as exception:
        if 'database' in str(exception) and 'does not exist' in str(exception):
            first_run_app.logger.info("You'll need to follow the documentation to create the database.")
            first_run_app.logger.info("This isn't possible through Flask right now (issue \#15 in the Github repo).")
    else:
        while True:
            user_input = input('(C)ontinue, (D)rop all, or (E)xit?: ').lower()
            if user_input in ['d', 'drop', 'drop all']:
                db.drop_all()
                break
            elif user_input in ['c', 'continue']:
                break
            elif user_input in ['e', 'exit']:
                sys.exit()
            else:
                print('Can you try that again?')
        if most_recent_stored_block != most_recent_block:
            the_blocks = range(most_recent_stored_block + 1, most_recent_block + 1)
            lets_boogy(the_blocks, uniques)
        else:
            first_run_app.logger.info("Looks like you're all up-to-date")
            sys.exit()
