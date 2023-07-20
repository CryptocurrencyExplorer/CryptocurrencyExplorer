import logging
import sys
import click
from logging.handlers import RotatingFileHandler
from flask import Flask
from psycopg2 import errors
from sqlalchemy import create_engine, inspect
from sqlalchemy.sql import desc
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import close_all_sessions
import blockchain
from blockchain import SUPPORTED_COINS
from config import autodetect_config, autodetect_tables
from config import coin_name, rpcpassword, rpcport, rpcuser
from config import app_key, csrf_key, database_uri
from helpers import pre_boogie, bulk_of_first_run_or_cron, JSONRPC, JSONRPCException
from models import db, Blocks

EXPECTED_TABLES = {'addresses', 'address_summary', 'blocks', 'coinbasetxin', 'txs', 'txout', 'txin'}
# https://www.postgresql.org/docs/current/errcodes-appendix.html#ERRCODES-TABLE
UniqueViolation = errors.lookup('23505')
DiskFull = errors.lookup('53100')


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


def process_block(current_item):
    if current_item is not None:
        return f'Processing block {current_item} / {block_length}'


def lets_boogie(the_blocks, cryptocurrency):
    total_cumulative_difficulty, outstanding_coins = pre_boogie(the_blocks, db, cryptocurrency)
    with click.progressbar(the_blocks, item_show_func=process_block) as progress_bar:
        for block_height in progress_bar:
            try:
                bulk_of_first_run_or_cron(first_run_app, db, uniques,
                                          cryptocurrency, block_height,
                                          total_cumulative_difficulty,
                                          outstanding_coins,
                                          the_blocks)
            except(IntegrityError, UniqueViolation) as e:
                first_run_app.logger.error(f"ERROR: {str(e)}")
                db.session.rollback()
                db.session.close()
                sys.exit()
            # If disk is full we can't log anything.. so, shutdown.
            except DiskFull:
                first_run_app.logger.error(f"ERROR: Disk full! Shutting down..")
                db.session.rollback()
                db.session.close()
                sys.exit()


def detect_flask_config():
    app_key_default = False
    csrf_key_default = False
    if app_key == rb"""app_key""":
        first_run_app.logger.error("Go into config.py and change the app_key!")
        app_key_default = True
    if csrf_key == "csrf_key":
        first_run_app.logger.error("Go into config.py and change the csrf_key!")
        csrf_key_default = False
    if app_key_default or csrf_key_default:
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
            # since this will catch if nothing can be detected in the for loop
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
        #  Though, obviously segwit won't be manipulated/added to if the specific chain doesn't support it.
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

    try:
        if autodetect_config:
            detect_flask_config()
        try:
            rpcurl = f"http://127.0.0.1:{rpcport}"
            crypto_currency = JSONRPC(rpcurl, rpcuser, rpcpassword)
        except(JSONRPCException, ValueError):
            first_run_app.logger.error("One/all of these are wrong: rpcuser/rpcpassword/rpcport. Fix this in config.py")
            sys.exit()

        uniques = detect_coin(crypto_currency)

        if autodetect_tables:
            detect_tables()

        most_recent_block = crypto_currency.getblockcount()
        if most_recent_block is None:
            first_run_app.logger.error("Doesn't look like you have the daemon running. Fix this.")
            sys.exit()
        try:
            most_recent_stored_block = db.session.query(Blocks).order_by(desc('height')).first().height
        except AttributeError:
            all_the_blocks = range(0, most_recent_block + 1)
            block_length = len(all_the_blocks)
            lets_boogie(all_the_blocks, crypto_currency)
        except OperationalError as exception:
            if 'database' in str(exception) and 'does not exist' in str(exception):
                first_run_app.logger.info("You'll need to follow the documentation to create the database.")
                first_run_app.logger.info("This isn't possible through Flask right now (issue #15 in the Github repo).")
        else:
            while True:
                user_input = input('(C)ontinue, (D)rop all, or (E)xit?: ').lower()
                if user_input in ['d', 'drop', 'drop all']:
                    try:
                        with first_run_app.app_context():
                            # https://docs.sqlalchemy.org/en/14/orm/session_api.html#sqlalchemy.orm.sessionmaker.close_all
                            close_all_sessions()
                            db.drop_all()
                    except OperationalError as e_:
                        if 'DeadlockDetected' in str(e_):
                            first_run_app.logger.info("Looks like you have something else occupying the database.")
                            first_run_app.logger.info("This is probably cronjob.py. Shut it off and try this again.")
                        else:
                            print(str(e_))
                    sys.exit()
                elif user_input in ['c', 'continue']:
                    break
                elif user_input in ['e', 'exit', 'x', 'quit', 'leave']:
                    sys.exit()
                else:
                    print('Can you try that again?')
            if most_recent_stored_block != most_recent_block:
                all_the_blocks = range(most_recent_stored_block + 1, most_recent_block + 1)
                block_length = most_recent_block
                lets_boogie(all_the_blocks, crypto_currency)
            else:
                first_run_app.logger.info("Looks like you're all up-to-date")
                sys.exit()
    except KeyboardInterrupt:
        first_run_app.logger.info("KeyboardInterrupt caught.")
        db.session.close()
        sys.exit()
