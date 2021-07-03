import datetime
import decimal
from sqlalchemy.sql import desc
from models import Blocks


def format_time(timestamp):
    return datetime.datetime.fromtimestamp(timestamp)


def generate_front_page_blocks(db):
    front_page_blocks = {}
    twenty_five_latest = db.session.query(Blocks).order_by(desc('height')).limit(25).all()
    for each in twenty_five_latest:
        front_page_blocks[each.height] = {}
        front_page_blocks[each.height]['block_height'] = each.height
        front_page_blocks[each.height]['block_hash'] = each.hash
        front_page_blocks[each.height]['total_transactions'] = each.transactions
        front_page_blocks[each.height]['formatted_time'] = each.time
        front_page_blocks[each.height]['difficulty'] = each.difficulty
        front_page_blocks[each.height]['total_out'] = f'{each.value_out:.8f}'
        # TODO
        front_page_blocks[each.height]['fees'] = decimal.Decimal(0.00000000)
    return sorted(front_page_blocks.items(), reverse=True)