import datetime
import decimal
import json
import requests
import sys

EMPTY = []


def format_time(timestamp):
    return datetime.datetime.fromtimestamp(timestamp)


def chain_age(timestamp, genesis_time):
    the_timestamp = datetime.datetime.fromtimestamp(timestamp)
    genesis_timestamp = datetime.datetime.fromtimestamp(genesis_time)
    difference = the_timestamp - genesis_timestamp
    difference_in_days = decimal.Decimal(difference.total_seconds()) / decimal.Decimal(86400)
    return f"{difference_in_days:.2f}"


def format_size(tx_size):
    return tx_size / 1000.0


def format_eight_zeroes(the_item):
    if the_item == 0:
        return '0.00000000'
    else:
        return format(the_item, '.8f')


def pre_boogie(the_blocks, db, cryptocurrency):
    from sqlalchemy.sql import desc
    from models import Blocks
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
    return total_cumulative_difficulty, outstanding_coins


def bulk_of_first_run_or_cron(name_of_flask_app, db, uniques, cryptocurrency, block_height,
                              total_cumulative_difficulty, outstanding_coins, the_blocks):
    from models import Addresses, AddressSummary, Blocks, CoinbaseTXIn, TXIn, TXs, TxOut
    total_value_out = decimal.Decimal(0.0)
    total_value_out_sans_coinbase = decimal.Decimal(0.0)
    tx_value_out = decimal.Decimal(0.0)
    tx_value_in = decimal.Decimal(0.0)
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
                        total_value_out_sans_coinbase += vout['value']
                    else:
                        outstanding_coins += vout['value']
                    the_address = vout['scriptPubKey']['addresses'][0]

                    # address stuff
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
                    ###
                    tx_value_out += vout['value']
                    commit_transaction_out = TxOut(txid=this_transaction,
                                                   n=vout['n'],
                                                   value=vout['value'],
                                                   scriptpubkey=vout['scriptPubKey']['asm'],
                                                   address=the_address,
                                                   linked_txid=None,
                                                   spent=False)
                    db.session.add(commit_transaction_out)
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
                        tx_value_in += prevout_value
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
                                name_of_flask_app.logger.error(
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
                             total_out=tx_value_out,
                             total_in=tx_value_in,
                             fee=tx_total_fees)
                db.session.add(the_tx)
                prev_out_total_out = decimal.Decimal(0.0)
                total_value_out_sans_coinbase = decimal.Decimal(0.0)
                tx_value_out = decimal.Decimal(0.0)
                tx_value_in = decimal.Decimal(0.0)
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


class JSONRPC(object):
    __id_count = 0

    def __init__(self, url, rpc_user, rpc_password, rpc_method=None, timeout=30):
        self.__url = url
        self.__user = rpc_user
        self.__password = rpc_password
        self.__method_name = rpc_method
        self.__timeout = timeout

    def __getattr__(self, method_name):
        return JSONRPC(self.__url, self.__user, self.__password, method_name, timeout=self.__timeout)

    def __call__(self, *args):
        response = None
        headers = {'Content-type': 'application/json'}
        JSONRPC.__id_count += 1
        postdata = json.dumps({'version': '1.1', 'method': self.__method_name,
                               'params': args, 'id': JSONRPC.__id_count})
        try:
            response = requests.post(self.__url,
                                     headers=headers,
                                     data=postdata,
                                     timeout=self.__timeout,
                                     auth=(self.__user,
                                           self.__password))
            # TODO - this is better than float, but need to make sure we properly format
            # TODO - scientific notation. 1+E8 isn't slick looking.
            response = response.json(parse_float=decimal.Decimal)
        except Exception:
            return
        if response.get('error') is not None:
            print(response['error'])
            raise JSONRPCException(response['error'])
        elif 'result' not in response:
            raise JSONRPCException({'code': -343,
                                    'message': 'missing JSON-RPC result'})
        else:
            return response['result']


class JSONRPCException(Exception):
    def __init__(self, rpc_error):
        parent_args = []
        try:
            parent_args.append(rpc_error['message'])
        except:
            pass
        Exception.__init__(self, *parent_args)
        self.error = rpc_error
        self.code = rpc_error['code'] if 'code' in rpc_error else None
        self.message = rpc_error['message'] if 'message' in rpc_error else None

    def __str__(self):
        return '%d: %s' % (self.code, self.message)

    def __repr__(self):
        return '<%s \'%s\'>' % (self.__class__.__name__, self)
