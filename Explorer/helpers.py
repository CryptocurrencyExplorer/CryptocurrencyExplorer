import datetime
import decimal
from sqlalchemy.sql import desc
from models import Blocks

def format_difficulty(difficulty):
    return f'{decimal.Decimal(difficulty):.8f}'


def format_transaction_length(transactions):
    return len(transactions)


def format_time(timestamp):
    return datetime.datetime.fromtimestamp(timestamp)


def generate_front_page_blocks(db):
    front_page_blocks = {}
    twenty_five_latest = db.session.query(Blocks).order_by(desc('height')).limit(25).all()
    for each in twenty_five_latest:
        front_page_blocks[each.height] = {}
        front_page_blocks[each.height]['block_height'] = each.height
        front_page_blocks[each.height]['block_hash'] = each.hash
        # TODO
        how_many_transactions = 9001
        # TODO
        front_page_blocks[each.height]['total_transactions'] = 9001
        front_page_blocks[each.height]['formatted_time'] = each.time
        front_page_blocks[each.height]['difficulty'] = each.difficulty
        # TODO
        front_page_blocks[each.height]['total_out'] = f'{each.value_out:.8f}'
        if how_many_transactions == 1:
            # TODO
            front_page_blocks[each.height]['fees'] = decimal.Decimal(0.00000000)
        else:
            # TODO
            front_page_blocks[each.height]['fees'] = decimal.Decimal(0.00000000)
    return sorted(front_page_blocks.items(), reverse=True)


def generate_previous_and_next_block(cryptocurrency, the_block):
    if the_block['height'] != 0:
        previous_hash_height = the_block['height'] - 1
        previous_block_raw_hash = cryptocurrency.getblockhash(previous_hash_height)
        previous_block = cryptocurrency.getblock(previous_block_raw_hash)
    else:
        previous_block = {'hash': None}
    if the_block['height'] != cryptocurrency.getblockcount():
        next_hash_height = the_block['height'] + 1
        next_block_raw_hash = cryptocurrency.getblockhash(next_hash_height)
        next_block = cryptocurrency.getblock(next_block_raw_hash)
    else:
        next_block = {'hash': None}
    return previous_block['hash'], next_block['hash']