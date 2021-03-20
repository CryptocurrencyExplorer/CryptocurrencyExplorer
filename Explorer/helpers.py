import datetime
import decimal


def format_difficulty(difficulty):
    return f'{decimal.Decimal(difficulty):.8f}'


def format_transaction_length(transactions):
    return len(transactions)


def format_time(timestamp):
    return datetime.datetime.fromtimestamp(timestamp)


def generate_front_page_blocks(cryptocurrency, db):
    front_page_blocks = {}
    total_blocks = cryptocurrency.getblockcount() + 1
    for each in range(total_blocks-25, total_blocks):
        front_page_blocks[each] = {}
        block_raw_hash = cryptocurrency.getblockhash(each)
        the_block = cryptocurrency.getblock(block_raw_hash)
        block_height = the_block['height']
        block_hash = the_block['hash']
        block_transactions = the_block['tx']
        how_many_transactions = len(the_block['tx'])
        block_time = the_block['time']
        block_difficulty = the_block['difficulty']
        front_page_blocks[each]['block_hash'] = block_raw_hash
        front_page_blocks[each]['block_height'] = block_height
        front_page_blocks[each]['formatted_time'] = block_time
        front_page_blocks[each]['total_transactions'] = how_many_transactions
        value_out = decimal.Decimal(0.00000000)
        for number, this_transaction in enumerate(the_block['tx']):
            if block_height != 0:
                raw_block_tx = cryptocurrency.getrawtransaction(this_transaction, 1)
                value_out += sum([x['value'] for x in raw_block_tx['vout']])
                # This is filler for the time being
                fees = 0
            else:
                raw_block_tx = {}
                value_out = decimal.Decimal(0.00000000)
                fees = decimal.Decimal(0.00000000)
        front_page_blocks[each]['total_out'] = f'{value_out:.8f}'
        front_page_blocks[each]['difficulty'] = block_difficulty
        if how_many_transactions == 1:
            front_page_blocks[each]['fees'] = decimal.Decimal(0.00000000)
        else:
            front_page_blocks[each]['fees'] = decimal.Decimal(0.00000000)
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