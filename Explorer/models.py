from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


class Addresses(db.Model):
    __tablename__ = 'addresses'
    address = db.Column(db.String,
                        unique=False,
                        nullable=False,
                        primary_key=True)
    amount = db.Column(db.Numeric,
                       unique=False,
                       nullable=False)
    n = db.Column(db.Integer,
                  unique=False,
                  nullable=False)
    in_block = db.Column(db.Integer,
                         unique=False,
                         nullable=False)
    transaction = db.Column(db.String,
                            index=True,
                            unique=False,
                            nullable=False)
    # input or output, 0 or 1
    type = db.Column(db.Boolean,
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
                       nullable=False,
                       index=True)
    hash = db.Column(db.String,
                     primary_key=True,
                     unique=True)
    version = db.Column(db.Integer,
                        unique=False,
                        nullable=False)
    prevhash = db.Column(db.String,
                         unique=False,
                         nullable=False,
                         index=True)
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
    outstanding = db.Column(db.Numeric,
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


class TXs(db.Model):
    __tablename__ = 'txs'
    id = db.Column(db.Integer,
                   primary_key=True)
    txid = db.Column(db.String,
                     unique=False,
                     nullable=False,
                     index=True)
    block_height = db.Column(db.Integer,
                             unique=False,
                             nullable=False)
    size = db.Column(db.Numeric,
                     unique=False,
                     nullable=False)
    n = db.Column(db.Integer,
                  nullable=False,
                  unique=False)
    version = db.Column(db.Integer,
                        unique=False,
                        nullable=False)
    locktime = db.Column(db.Integer,
                         unique=False,
                         nullable=False)
    total_out = db.Column(db.Numeric,
                          unique=False,
                          nullable=False)
    total_in = db.Column(db.Numeric,
                         unique=False,
                         nullable=False)
    fee = db.Column(db.Numeric,
                    unique=False,
                    nullable=False)


class CoinbaseTXIn(db.Model):
    __tablename__ = 'coinbasetxin'
    block_height = db.Column(db.Integer,
                             unique=False,
                             nullable=False,
                             primary_key=True)
    txid = db.Column(db.String,
                     unique=False,
                     nullable=False,
                     index=True)
    scriptsig = db.Column(db.String,
                          unique=False,
                          nullable=True)
    sequence = db.Column(db.BIGINT,
                         unique=False,
                         nullable=False)
    witness = db.Column(db.String,
                        unique=False,
                        nullable=True)
    spent = db.Column(db.Boolean,
                      unique=False,
                      nullable=True)


class TXIn(db.Model):
    __tablename__ = 'txin'
    id = db.Column(db.Integer,
                   primary_key=True)
    block_height = db.Column(db.Integer,
                             unique=False,
                             nullable=False,
                             index=True)
    txid = db.Column(db.String,
                     unique=False,
                     nullable=False,
                     index=True)
    n = db.Column(db.Integer,
                  unique=False,
                  nullable=False)
    scriptsig = db.Column(db.String,
                          unique=False,
                          nullable=True)
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
                             nullable=False,
                             index=True)
    prevout_n = db.Column(db.Integer,
                          unique=False,
                          nullable=False,
                          index=True)
    address = db.Column(db.String,
                        unique=False,
                        nullable=False)
    value = db.Column(db.Numeric,
                      unique=False,
                      nullable=False)


class TxOut(db.Model):
    __tablename__ = 'txout'
    id = db.Column(db.Integer,
                   primary_key=True)
    block_height = db.Column(db.Integer,
                             unique=False,
                             nullable=False,
                             index=True)
    txid = db.Column(db.String,
                     unique=False,
                     nullable=False,
                     index=True)
    n = db.Column(db.Integer,
                  unique=False,
                  nullable=False,
                  index=True)
    value = db.Column(db.Numeric,
                      unique=False,
                      nullable=False)
    scriptpubkey = db.Column(db.String,
                             unique=False,
                             nullable=False)
    address = db.Column(db.String,
                        unique=False,
                        nullable=False)
    linked_txid = db.Column(db.String,
                            unique=False,
                            nullable=True)
    spent = db.Column(db.Boolean,
                      unique=False,
                      nullable=False)
