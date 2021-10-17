from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


class Addresses(db.Model):
    __tablename__ = 'addresses'
    id = db.Column(db.Integer,
                   primary_key=True)
    address = db.Column(db.String,
                        unique=False,
                        nullable=False)
    amount = db.Column(db.Numeric,
                       unique=False,
                       nullable=False)
    in_block = db.Column(db.Integer,
                         unique=False,
                         nullable=False)
    transaction = db.Column(db.String,
                            unique=False,
                            nullable=False)
    datetime = db.Column(db.Integer,
                         unique=False,
                         nullable=False)


class AddressSummary(db.Model):
    __tablename__ = 'address_summary'
    address = db.Column(db.String,
                        primary_key=True)
    balance = db.Column(db.Numeric,
                        unique=False,
                        nullable=False)
    transactions_in = db.Column(db.Integer,
                                unique=False,
                                nullable=False)
    received = db.Column(db.Numeric,
                         unique=False,
                         nullable=False)
    transactions_out = db.Column(db.Integer,
                                 unique=False,
                                 nullable=False)
    sent = db.Column(db.Numeric,
                     unique=False,
                     nullable=False)


class Blocks(db.Model):
    __tablename__ = 'blocks'
    height = db.Column(db.Integer,
                       unique=True,
                       nullable=False)
    hash = db.Column(db.String,
                     primary_key=True)
    version = db.Column(db.Integer,
                        unique=False,
                        nullable=False)
    prevhash = db.Column(db.String,
                         unique=False,
                         nullable=False)
    nexthash = db.Column(db.String,
                         unique=False,
                         nullable=False)
    merkleroot = db.Column(db.String,
                           unique=False,
                           nullable=False)
    time = db.Column(db.Integer,
                     unique=False,
                     nullable=False)
    bits = db.Column(db.String,
                     unique=False,
                     nullable=False)
    nonce = db.Column(db.BIGINT,
                      unique=False,
                      nullable=False)
    size = db.Column(db.Integer,
                     unique=False,
                     nullable=False)
    difficulty = db.Column(db.Numeric,
                           unique=False,
                           nullable=False)
    cumulative_difficulty = db.Column(db.Numeric,
                                      unique=False,
                                      nullable=False)
    value_out = db.Column(db.Numeric,
                          unique=False,
                          nullable=False)
    transactions = db.Column(db.Integer,
                             unique=False,
                             nullable=False)
    transaction_fees = db.Column(db.Numeric,
                                 unique=False,
                                 nullable=False)


class BlockTXs(db.Model):
    __tablename__ = 'blocktxs'
    id = db.Column(db.Integer,
                   primary_key=True)
    block_height = db.Column(db.Integer,
                             nullable=False)
    n = db.Column(db.Integer,
                  nullable=False)
    tx_id = db.Column(db.String,
                      nullable=False)


class TXs(db.Model):
    __tablename__ = 'txs'
    txid = db.Column(db.String,
                     primary_key=True)
    version = db.Column(db.Integer,
                        unique=False,
                        nullable=False)
    locktime = db.Column(db.Integer,
                         unique=False,
                         nullable=False)


class TXIn(db.Model):
    __tablename__ = 'txin'
    id = db.Column(db.Integer,
                   primary_key=True)
    block_height = db.Column(db.Integer,
                             unique=False,
                             nullable=False)
    tx_id = db.Column(db.String,
                      unique=False,
                      nullable=False)
    n = db.Column(db.Integer,
                  unique=False,
                  nullable=False)
    scriptsig = db.Column(db.String,
                          unique=False,
                          nullable=False)
    sequence = db.Column(db.BIGINT,
                         unique=False,
                         nullable=False)
    witness = db.Column(db.String,
                        unique=False,
                        nullable=True)
    coinbase = db.Column(db.Boolean,
                         unique=False,
                         nullable=True)
    spent = db.Column(db.Boolean,
                      unique=False,
                      nullable=True)
    prevout_hash = db.Column(db.String,
                             unique=False,
                             nullable=True)
    prevout_n = db.Column(db.Integer,
                          unique=False,
                          nullable=True)


class TxOut(db.Model):
    __tablename__ = 'txout'
    id = db.Column(db.Integer,
                   primary_key=True)
    n = db.Column(db.Integer,
                  unique=False,
                  nullable=False)
    value = db.Column(db.Numeric,
                      unique=False,
                      nullable=False)
    scriptpubkey = db.Column(db.String,
                             unique=False,
                             nullable=False)
    address = db.Column(db.String,
                        unique=False,
                        nullable=False)
    linked_tx_id = db.Column(db.String,
                             unique=False,
                             nullable=True)
    this_tx_id = db.Column(db.String,
                           unique=False,
                           nullable=True)
    spent = db.Column(db.Boolean,
                      unique=False,
                      nullable=False)
