import logging
import sys
from pathlib import Path
from flask import Flask
from logging.handlers import RotatingFileHandler
from psycopg2 import errors
from sqlalchemy.sql import desc
import blockchain
from config import coin_name, rpcpassword, rpcport, rpcuser
from config import database_uri
from sqlalchemy.exc import IntegrityError
from helpers import bulk_of_first_run_or_cron, JSONRPC, pre_boogie
from models import db, Blocks

EXPECTED_TABLES = {'addresses', 'address_summary', 'blocks', 'coinbasetxin', 'txs', 'txout', 'txin'}
UniqueViolation = errors.lookup('23505')
DiskFull = errors.lookup('53100')


def create_app():
    the_cronjob = Flask(__name__)
    the_cronjob.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    the_cronjob.config['SQLALCHEMY_DATABASE_URI'] = database_uri
    # setup RotatingFileHandler with maxBytes set to 25MB
    this_directory = Path(__file__).parent
    cronjob_log = Path(this_directory, 'explorer_cronjob.log')
    rotating_log = RotatingFileHandler(cronjob_log, maxBytes=25000000, backupCount=6)
    the_cronjob.logger.addHandler(rotating_log)
    rotating_log.setFormatter(logging.Formatter(fmt='[%(asctime)s] / %(levelname)s in %(module)s: %(message)s'))
    the_cronjob.logger.setLevel(logging.INFO)
    db.init_app(the_cronjob)
    return the_cronjob


def lets_boogie(the_blocks, uniques, cryptocurrency):
    outstanding_coins, total_cumulative_difficulty = pre_boogie(db, cryptocurrency, most_recent_stored_block)
    for block_height in the_blocks:
        try:
            outstanding_coins, total_cumulative_difficulty = bulk_of_first_run_or_cron(cronjob, db, uniques,
                                                                                       cryptocurrency, block_height,
                                                                                       most_recent_block,
                                                                                       outstanding_coins,
                                                                                       total_cumulative_difficulty)
        except(IntegrityError, UniqueViolation) as e:
            cronjob.logger.error(f"ERROR: {str(e)}")
            db.session.rollback()
            db.session.close()
            sys.exit()
        # If disk is full we can't log anything.. so, shutdown.
        except DiskFull:
            cronjob.logger.error(f"ERROR: Disk full! Shutting down..")
            db.session.rollback()
            db.session.close()
            sys.exit()
        else:
            cronjob.logger.info(f"committed block {block_height}")


if __name__ == '__main__':
    cronjob = create_app()
    cronjob.app_context().push()

    rpcurl = f"http://127.0.0.1:{rpcport}"
    crypto_currency = JSONRPC(rpcurl, rpcuser, rpcpassword)

    most_recent_block = crypto_currency.getblockcount()

    most_recent_stored_block = db.session.query(Blocks).order_by(desc('height')).first().height
    db.session.remove()

    coin_name_in_config = coin_name.capitalize()
    the_coin = getattr(blockchain, coin_name_in_config)()
    the_uniques = the_coin.unique

    if most_recent_stored_block != most_recent_block:
        all_the_blocks = range(most_recent_stored_block + 1, most_recent_block + 1)
        lets_boogie(all_the_blocks, the_uniques, crypto_currency)
    else:
        sys.exit()
