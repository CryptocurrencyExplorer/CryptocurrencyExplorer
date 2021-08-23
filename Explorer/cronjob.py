import decimal
import logging
import sys
from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException
from flask import Flask
from logging.handlers import RotatingFileHandler
from sqlalchemy.sql import desc
from config import rpcpassword, rpcport, rpcuser
from config import database_uri
from models import db
from models import Addresses, AddressSummary, Blocks, BlockTXs, CoinbaseTxIn
from models import TXs, LinkedTxOut, TxOut, LinkedTxOut, TXIn

# This is a placeholder to indicate the transaction is empty
EMPTY = ''
EXPECTED_TABLES = {'addresses', 'address_summary', 'blocks', 'blocktxs', 'coinbase_txin', 'txs', 'linked_txout',
                   'txout', 'linked_txin', 'txin'}


def create_app():
    cronjob = Flask(__name__)
    cronjob.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    cronjob.config['SQLALCHEMY_DATABASE_URI'] = database_uri
    # setup RotatingFileHandler with maxBytes set to 25MB
    rotating_log = RotatingFileHandler('explorer_cronjob.log', maxBytes=25000000, backupCount=6)
    cronjob.logger.addHandler(rotating_log)
    rotating_log.setFormatter(logging.Formatter(fmt='[%(asctime)s] / %(levelname)s in %(module)s: %(message)s'))
    cronjob.logger.setLevel(logging.INFO)
    db.init_app(cronjob)
    return cronjob


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

    for block_height in the_blocks:
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
                #print(f'vin: {how_many_vin}')
                #print(f'vout: {how_many_vout}')

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
                prev_block_hash='0000000000000000000000000000000000000000000000000000000000000000'
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
        cronjob.logger.info(f"committed block {block_height}")


if __name__ == '__main__':
    cronjob = create_app()
    cronjob.app_context().push()

    cryptocurrency = AuthServiceProxy(f"http://{rpcuser}:{rpcpassword}@127.0.0.1:{rpcport}")

    most_recent_block = cryptocurrency.getblockcount()

    most_recent_stored_block = db.session.query(Blocks).order_by(desc('height')).first().height

    if most_recent_stored_block != most_recent_block:
        the_blocks = range(most_recent_stored_block + 1, most_recent_block + 1)
        lets_boogy(the_blocks)
    else:
        sys.exit()