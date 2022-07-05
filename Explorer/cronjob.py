import decimal
import logging
import sys
from pathlib import Path
from flask import Flask
from logging.handlers import RotatingFileHandler
from sqlalchemy.sql import desc
import blockchain
from config import coin_name, rpcpassword, rpcport, rpcuser
from config import database_uri
from sqlalchemy.exc import IntegrityError
from helpers import JSONRPC, JSONRPCException
from models import db, Addresses, AddressSummary, Blocks, CoinbaseTXIn, TXs, TxOut, TXIn

# This is a placeholder to indicate the transaction is empty
EMPTY = ''
EXPECTED_TABLES = {'addresses', 'address_summary', 'blocks', 'coinbasetxin', 'txs', 'txout', 'txin'}


def create_app():
    cronjob = Flask(__name__)
    cronjob.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    cronjob.config['SQLALCHEMY_DATABASE_URI'] = database_uri
    # setup RotatingFileHandler with maxBytes set to 25MB
    this_directory = Path(__file__).parent
    cronjob_log = Path(this_directory, 'explorer_cronjob.log')
    rotating_log = RotatingFileHandler(cronjob_log, maxBytes=25000000, backupCount=6)
    cronjob.logger.addHandler(rotating_log)
    rotating_log.setFormatter(logging.Formatter(fmt='[%(asctime)s] / %(levelname)s in %(module)s: %(message)s'))
    cronjob.logger.setLevel(logging.INFO)
    db.init_app(cronjob)
    return cronjob


def lets_boogy(the_blocks, uniques, cryptocurrency):
    if the_blocks[0] == 0:
        total_cumulative_difficulty = decimal.Decimal(0.0)
        outstanding_coins = decimal.Decimal(0.0)
    else:
        total_cumulative_difficulty = db.session.query(Blocks).order_by(
                                      desc('cumulative_difficulty')).first().cumulative_difficulty
        outstanding_coins = db.session.query(Blocks).order_by(
                            desc('outstanding')).first().outstanding
        current_block = db.session.query(Blocks).order_by(desc('height')).first()
        if current_block.nexthash == 'PLACEHOLDER':
            next_block_hash = cryptocurrency.getblockhash(current_block.height + 1)
            current_block.nexthash = next_block_hash
            db.session.commit()
            db.session.remove()

    for block_height in the_blocks:
        try:
            total_value_out = decimal.Decimal(0.0)
            total_value_out_sans_coinbase = decimal.Decimal(0.0)
            prev_out_total_out = decimal.Decimal(0.0)
            prev_out_total_out_with_fees = decimal.Decimal(0.0)
            block_total_fees = decimal.Decimal(0.0)
            block_raw_hash = cryptocurrency.getblockhash(block_height)
            the_block = cryptocurrency.getblock(block_raw_hash)
            total_cumulative_difficulty += decimal.Decimal(the_block['difficulty'])
            raw_block_transactions = the_block['tx']
            how_many_transactions = len(raw_block_transactions)

            # Probably better to just take the latest block's height and minus this block's height to get this
            # block_confirmations = cryptocurrency.getblockcount() + 1 - block_height
            for number, this_transaction in enumerate(raw_block_transactions):
                try:
                    raw_block_tx = cryptocurrency.getrawtransaction(this_transaction, 1)
                except JSONRPCException as e:
                    pass
                    # if 'No information available about transaction' in str(e):
                    # TODO - Add something to indicate this transaction is unavailable
                else:
                    if this_transaction in uniques['tx']:
                        if uniques['tx'][this_transaction] == EMPTY:
                            pass
                    else:
                        for vout in raw_block_tx['vout']:
                            if number != 0:
                                the_address = vout['scriptPubKey']['addresses'][0]
                                total_value_out_sans_coinbase += vout['value']
                                address_lookup = db.session.query(Addresses).filter_by(
                                    address=the_address).one_or_none()
                                if address_lookup is None:
                                    commit_address_transaction = Addresses(address=the_address,
                                                                           amount=vout['value'],
                                                                           n=vout['n'],
                                                                           in_block=block_height,
                                                                           transaction=this_transaction)
                                    db.session.add(commit_address_transaction)

                                address_summary_lookup = db.session.query(AddressSummary).filter_by(
                                    address=the_address).one_or_none()
                                if address_summary_lookup is None:
                                    address_summary = AddressSummary(address=the_address,
                                                                     balance=vout['value'],
                                                                     transactions_in=1,
                                                                     received=decimal.Decimal(0.00000000),
                                                                     transactions_out=0,
                                                                     sent=0.00000000)
                                    db.session.add(address_summary)
                                else:
                                    # TODO - all of this
                                    address_summary_lookup.balance = decimal.Decimal(0.00000000)
                                    address_summary_lookup.transactions_in = 1
                                    address_summary_lookup.received = decimal.Decimal(0.00000000)
                                    address_summary_lookup.transaction_out = 1
                                    address_summary_lookup.sent = 1
                                    db.session.commit()
                                commit_transaction_out = TxOut(txid=this_transaction,
                                                               n=vout['n'],
                                                               value=vout['value'],
                                                               scriptpubkey=vout['scriptPubKey']['asm'],
                                                               address=the_address,
                                                               linked_txid=None,
                                                               spent=False)
                                db.session.add(commit_transaction_out)
                            else:
                                outstanding_coins += vout['value']
                            total_value_out += vout['value']

                        for vin_num, vin in enumerate(raw_block_tx['vin']):
                            if number == 0 and vin_num == 0:
                                commit_coinbase = CoinbaseTXIn(block_height=block_height,
                                                               txid=this_transaction,
                                                               scriptsig=vin['coinbase'],
                                                               sequence=vin['sequence'],
                                                               # TODO - This needs pulled from bootstrap
                                                               # TODO - Witness actually needs supported
                                                               witness=None,
                                                               spent=False)
                                db.session.add(commit_coinbase)
                            else:
                                previous_transaction = cryptocurrency.getrawtransaction(vin['txid'], 1)
                                prev_txid = previous_transaction['txid']
                                this_prev_vin = previous_transaction['vout'][vin['vout']]
                                the_prevout_n = this_prev_vin['n']
                                prevout_value = this_prev_vin['value']
                                prev_out_total_out += prevout_value
                                prevout_address = this_prev_vin['scriptPubKey']['addresses'][0]
                                commit_transaction_in = TXIn(block_height=block_height,
                                                             txid=this_transaction,
                                                             n=number,
                                                             scriptsig=vin['scriptSig']['asm'],
                                                             sequence=vin['sequence'],
                                                             # TODO - This needs pulled from bootstrap
                                                             # TODO - Witness actually needs supported
                                                             witness=None,
                                                             spent=False,
                                                             prevout_hash=prev_txid,
                                                             prevout_n=the_prevout_n)
                                cb_prev_tx = db.session.query(CoinbaseTXIn).filter_by(txid=prev_txid).one_or_none()
                                if cb_prev_tx is not None:
                                    cb_prev_tx.spent = True
                                    db.session.add(cb_prev_tx)
                                else:
                                    the_prev_tx = db.session.query(TXIn).filter_by(txid=prev_txid).first()
                                    if the_prev_tx is not None:
                                        the_prev_tx.spent = True
                                        db.session.add(the_prev_tx)
                                    else:
                                        # This shouldn't happen, but just in case..
                                        cronjob.logger.error(
                                            f"ERROR: Transaction {prev_txid} not found in TXIn or CoinbaseTXIn")
                                        sys.exit()
                                db.session.add(commit_transaction_in)
                        tx_total_fees = prev_out_total_out - total_value_out_sans_coinbase
                        outstanding_coins -= tx_total_fees
                        block_total_fees += tx_total_fees
                        the_tx = TXs(txid=this_transaction,
                                     block_height=block_height,
                                     size=raw_block_tx['size'],
                                     n=number,
                                     version=raw_block_tx['version'],
                                     locktime=raw_block_tx['locktime'],
                                     total_out=total_value_out,
                                     fee=tx_total_fees)
                        db.session.add(the_tx)
                        prev_out_total_out = decimal.Decimal(0.0)
                        total_value_out_sans_coinbase = decimal.Decimal(0.0)
            if block_height == 0:
                prev_block_hash = uniques['genesis']['prev_hash']
                next_block_hash = the_block['nextblockhash']
            elif block_height != the_blocks[-1]:
                prev_block_hash = the_block['previousblockhash']
                next_block_hash = the_block['nextblockhash']
            else:
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
                                      outstanding=outstanding_coins,
                                      value_out=total_value_out,
                                      transactions=how_many_transactions,
                                      transaction_fees=block_total_fees)
            db.session.add(this_blocks_info)
            this_block_finished = True
            if this_block_finished:
                db.session.commit()
                db.session.close()
        except IntegrityError as e:
            cronjob.logger.error(f"ERROR: {str(e)}")
            db.session.rollback()
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
        lets_boogy(all_the_blocks, the_uniques, crypto_currency)
    else:
        sys.exit()
