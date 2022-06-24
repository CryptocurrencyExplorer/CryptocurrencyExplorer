# ~/venv/bin/pip install Flask Flask-SQLALchemy Flask-WTF gunicorn psycopg2-binary python-bitcoinrpc Werkzeug
# apt install postgresql postgresql-client
# ----------------------------------------------
# Use Python 3.3+ because of `decimal` issues:
# https://docs.sqlalchemy.org/en/14/core/type_basics.html#sqlalchemy.types.Numeric
import logging
import sys
from decimal import Decimal
from logging.handlers import RotatingFileHandler
from flask import Flask, jsonify, make_response, send_from_directory
from flask import redirect, request, url_for, render_template, session
from flask.json import JSONEncoder
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFError, CSRFProtect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool
from sqlalchemy.sql import desc
from werkzeug.middleware.proxy_fix import ProxyFix
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length
import blockchain
from config import coin_name, rpcpassword, rpcport, rpcuser
from config import app_key, csrf_key, database_uri, program_name
from helpers import chain_age, format_fee, format_time, JSONRPC, JSONRPCException
from models import db, Blocks, CoinbaseTXIn, TXs, TXIn, TxOut


class DecimalEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        return JSONEncoder.default(self, obj)


def create_app(the_csrf):
    prep_application = Flask(__name__)
    prep_application.debug = False
    prep_application.json_encoder = DecimalEncoder
    # setup RotatingFileHandler with maxBytes set to 25MB
    rotating_log = RotatingFileHandler('cryptocurrency_explorer.log', maxBytes=25000000, backupCount=6)
    prep_application.logger.addHandler(rotating_log)
    rotating_log.setFormatter(logging.Formatter(fmt='[%(asctime)s] / %(levelname)s in %(module)s: %(message)s'))
    prep_application.logger.setLevel(logging.INFO)
    prep_application.secret_key = app_key
    if coin_name != '' or coin_name is not None:
        # check blockchain/README.md for this
        prep_application.config['COIN_NAME'] = coin_name.capitalize()
    else:
        prep_application.logger.error("coin_name in config.py needs to be set.")
        sys.exit()
    try:
        coin__uniques = getattr(blockchain, prep_application.config['COIN_NAME'])().unique
    # TypeError needs caught in case someone tries non-strings for the coin_name... for whatever reason?
    except(AttributeError, TypeError):
        prep_application.logger.error("coin_name in config.py is not a supported coin.")
        sys.exit()
    prep_application.config['JSONIFY_PRETTYPRINT_REGULAR'] = True
    prep_application.config['MAX_CONTENT_LENGTH'] = 256
    prep_application.config['PROGRAM_NAME'] = program_name
    # This appears to be an issue -- https://github.com/wtforms/flask-wtf/issues/521.
    # prep_application.config['REMEMBER_COOKIE_HTTPONLY'] = True
    #
    # prep_application.config['SESSION_COOKIE_HTTPONLY'] = True
    prep_application.config['SESSION_COOKIE_NAME'] = 'csrf_token'
    # prep_application.config['SESSION_COOKIE_SECURE'] = True
    prep_application.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    prep_application.config['SQLALCHEMY_DATABASE_URI'] = database_uri
    prep_application.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'poolclass': NullPool}
    prep_application.config['VERSION'] = 0.8
    prep_application.config['WTF_CSRF_SECRET_KEY'] = csrf_key
    prep_application.jinja_env.trim_blocks = True
    prep_application.jinja_env.lstrip_blocks = True
    prep_application.wsgi_app = ProxyFix(prep_application.wsgi_app, x_proto=1, x_host=1)
    db.init_app(prep_application)
    the_csrf.init_app(prep_application)
    rpcurl = f"http://127.0.0.1:{rpcport}"
    try:
        crypto_currency = JSONRPC(rpcurl, rpcuser, rpcpassword)
    except ValueError:
        prep_application.logger.error("One of these is wrong: rpcuser/rpcpassword/rpcport. Fix this in config.py.")
        sys.exit()
    return prep_application, coin__uniques, crypto_currency


csrf = CSRFProtect()
application, coin_uniques, cryptocurrency = create_app(csrf)
application.app_context().push()


# When first_run is executing, this needs to happen if we want to also view the explorer
# Not sure if I'm keeping this, or if this is the best way to approach this.
@application.errorhandler(SQLAlchemyError)
def sqlalchemy_error(error):
    db.session.rollback()


@application.before_request
def set_session_permanent():
    session.permanent = True


@application.errorhandler(CSRFError)
def handle_csrf_error(e):
    return render_template('404.html', error=e.description), 400


@application.errorhandler(400)
def handle_bad_request():
    error = 'bad request'
    return render_template("404.html", error=error), 400


@application.errorhandler(404)
def not_found(e):
    error = f'{request.environ["RAW_URI"]} was not found'
    return render_template("404.html", error=error), 404


@application.errorhandler(413)
def payload_too_large():
    error = f'payload too large'
    return render_template("404.html", error=error), 413


@application.errorhandler(414)
def uri_too_large():
    error = f'URI too large'
    return render_template("404.html", error=error), 414


@application.route('/robots.txt')
def robots():
    return send_from_directory(application.static_folder, 'robots.txt')


class SearchForm(FlaskForm):
    search = StringField('Search',
                         validators=[DataRequired(), Length(min=1, max=64)],
                         render_kw={"placeholder": "Search address, blocks, transactions, pubkey hash"})
    submit = SubmitField('Submit')


def validate_search(search_term):
    try:
        if int(search_term) in range(0, cryptocurrency.getblockcount() + 1):
            return redirect(url_for('block', block_hash_or_height=int(search_term)))
    except ValueError:
        try:
            if cryptocurrency.getblock(search_term)['hash']:
                return redirect(url_for('block', block_hash_or_height=search_term))
        except JSONRPCException:
            if cryptocurrency.validateaddress(search_term)['isvalid']:
                return redirect(url_for('api__validate_address', address=search_term))
            else:
                return make_response(jsonify({'message': 'todo',
                                              'error': 'todo'}), 200)


@application.get("/")
@application.post("/")
def index():
    form = SearchForm(request.form)
    count = request.args.get('count', default=50, type=int)
    try:
        if 1 <= count <= 500:
            count = count
        else:
            count = 25
    except ValueError:
        count = 1

    latest_block_height = int(db.session.query(Blocks).order_by(desc('height')).first().height)
    hi = request.args.get('hi', default=latest_block_height, type=int)
    try:
        if hi in range(0, latest_block_height + 1):
            hi = hi
        else:
            hi = 0
    except ValueError:
        hi = 0

    front_page_items = db.session.query(Blocks).where(Blocks.height <= hi).order_by(desc('height')).limit(count)
    genesis_timestamp = coin_uniques['genesis']['timestamp']

    if request.method == 'POST' and form.validate_on_submit():
        try:
            input_data = int(form.search.data)
        except ValueError:
            try:
                if db.session.query(Blocks).filter_by(hash=form.search.data).first():
                    return redirect(url_for('block', block_hash_or_height=form.search.data))
            except JSONRPCException:
                if cryptocurrency.validateaddress(form.search.data)['isvalid']:
                    return redirect(url_for('api__validate_address', address=form.search.data))
                else:
                    return redirect(url_for('index'))
        else:
            if input_data in range(0, latest_block_height + 1):
                return redirect(url_for('block', block_hash_or_height=input_data))
            else:
                return render_template('index.html',
                                       form=form,
                                       front_page_blocks=front_page_items,
                                       format_time=format_time,
                                       count=count,
                                       hi=hi,
                                       latest_block=latest_block_height,
                                       chain_age=chain_age,
                                       genesis_time=genesis_timestamp)
    return render_template('index.html',
                           form=form,
                           front_page_blocks=front_page_items,
                           format_time=format_time,
                           count=count,
                           hi=hi,
                           latest_block=latest_block_height,
                           chain_age=chain_age,
                           genesis_time=genesis_timestamp)


@application.get("/block/")
def redirect_to_block():
    return redirect(url_for('block', block_hash_or_height="0"))


@application.get("/block/<block_hash_or_height>/")
def block(block_hash_or_height):
    try:
        the_block_height = int(block_hash_or_height)
    except ValueError:
        try:
            block_lookup = db.session.query(Blocks).filter_by(hash=block_hash_or_height.lower()).first()
            the_block_height = int(block_lookup.height)
        except(AttributeError, ValueError):
            return render_template('404.html', error="Not a valid block height/hash"), 404

    latest_block_height = int(db.session.query(Blocks).order_by(desc('height')).first().height)
    if the_block_height in range(0, latest_block_height + 1):
        the_block = db.session.query(Blocks).filter_by(height=the_block_height).first()
        if the_block is not None:
            block_hash = the_block.hash
            if the_block_height != 0:
                previous_block_hash = the_block.prevhash
            else:
                previous_block_hash = None

            if the_block_height != latest_block_height:
                next_block_hash = the_block.nexthash
            else:
                next_block_hash = None

            transactions = db.session.query(TXs).filter_by(block_height=the_block_height).all()

            return render_template('block.html',
                                   block_hash=block_hash,
                                   previous_block_hash=previous_block_hash,
                                   next_block_hash=next_block_hash,
                                   block_height=the_block_height,
                                   version=the_block.version,
                                   merkle_root=the_block.merkleroot,
                                   time=the_block.time,
                                   formatted_time=format_time(the_block.time),
                                   difficulty=the_block.difficulty,
                                   bits=the_block.bits,
                                   cumulative_difficulty=the_block.cumulative_difficulty,
                                   nonce=the_block.nonce,
                                   the_transactions=transactions,
                                   outstanding=the_block.outstanding,
                                   value_out=the_block.value_out,
                                   transaction_fees=format_fee(the_block.transaction_fees),
                                   # TODO
                                   average_coin_age='?')
        else:
            return render_template('404.html', error="Not a valid block height/hash"), 404
    else:
        return render_template('404.html', error="Not a valid block height/hash"), 404


@application.get("/tx/")
def redirect_to_tx():
    return redirect(url_for('tx', transaction="INVALID_TRANSACTION"))


@application.get("/tx/<transaction>/")
def tx(transaction):
    # TODO - Transactions actually need done
    # Though, in order to finish this, addresses need done first
    check_transaction = db.session.query(TXs).filter_by(txid=transaction.lower()).first()
    if check_transaction is not None:
        coinbase = db.session.query(CoinbaseTXIn).filter_by(txid=transaction.lower()).one_or_none()
        txin = db.session.query(TXIn).filter_by(txid=transaction.lower()).all()
        txout = db.session.query(TxOut).filter_by(txid=transaction.lower()).all()
        if txin is not None and txout is not None:
            block_height_lookup = db.session.query(Blocks).filter_by(height=check_transaction.block_height).first()
            return render_template('transaction.html',
                                   coinbase=coinbase,
                                   the_datetime=format_time(block_height_lookup.time),
                                   block_height=check_transaction.block_height,
                                   inputs=txin,
                                   outputs=txout,
                                   this_transaction=transaction.lower(),
                                   fee=format_fee(check_transaction.fee),
                                   size=check_transaction.size)
        else:
            return render_template('404.html', error="Not a valid transaction"), 404
    else:
        return render_template('404.html', error="Not a valid transaction"), 404


@application.get("/api/")
def api_index():
    return render_template('api_index.html')


@application.get("/api/addressbalance/")
def redirect_to_api__address_balance():
    return redirect(url_for('api__validate_address', address="INVALID_ADDRESS"))


@application.get("/api/confirmations/")
def redirect_to_api__confirmations():
    return redirect(url_for('api__confirmations', userinput_block_height="0"))


@application.get("/api/rawtx/")
def redirect_to_api__rawtx():
    return redirect(url_for('api__rawtx', transaction=""))


@application.get("/api/receivedbyaddress/")
def redirect_to_api__received_by_address():
    return redirect(url_for('api__received_by_address', address="INVALID_ADDRESS"))


@application.get("/api/sentbyaddress/")
def redirect_to_api__sent_by_address():
    return redirect(url_for('api__sent_by_address', address="INVALID_ADDRESS"))


@application.get("/api/validateaddress/")
def redirect_to_api__validate_address():
    return redirect(url_for('api__validate_address', address="INVALID_ADDRESS"))


@application.get("/api/addressbalance/<address>/")
def api__address_balance(address):
    return make_response(jsonify({'message': 'todo',
                                  'error': 'todo'}), 200)


@application.get("/api/blockcount/")
def api__block_count():
    most_recent_height = db.session.query(Blocks).order_by(desc('height')).first().height
    return make_response(jsonify({'message': most_recent_height,
                                  'error': 'none'}), 200)


@application.get("/api/confirmations/<userinput_block_height>/")
def api__confirmations(userinput_block_height):
    try:
        userinput_block_height = int(userinput_block_height)
    except ValueError:
        # not a block number, check if it's a hash
        try:
            block_lookup = db.session.query(Blocks).filter_by(hash=userinput_block_height.lower()).first()
            if block_lookup is not None:
                user_block_height = int(block_lookup.height)
                latest_block_height = int(db.session.query(Blocks).order_by(desc('height')).first().height)
                block_confirmations = (latest_block_height + 1) - user_block_height
                return make_response(jsonify({'confirmations': block_confirmations,
                                              'error': 'none'}), 200)
            else:
                return make_response(jsonify({'message': 'This block hash/height is invalid',
                                              'error': 'invalid'}), 422)
        except JSONRPCException:
            return make_response(jsonify({'message': 'This block hash/height is invalid',
                                          'error': 'invalid'}), 422)
    else:
        latest_block_height = int(db.session.query(Blocks).order_by(desc('height')).first().height)
        # check if this is a block number like 0 or something else.
        # +1 because range() goes up to but doesn't include the number, so to include it we do +1
        if userinput_block_height in range(0, latest_block_height + 1):
            block_confirmations = (latest_block_height + 1) - userinput_block_height
            return make_response(jsonify({'confirmations': block_confirmations,
                                          'error': 'none'}), 200)
        else:
            return make_response(jsonify({'message': 'This block hash/height is invalid',
                                          'error': 'invalid'}), 422)


@application.get("/api/lastdifficulty/")
def api__last_difficulty():
    latest_difficulty = float(db.session.query(Blocks).order_by(desc('height')).first().difficulty)
    return make_response(jsonify({'message': latest_difficulty,
                                  'error': 'none'}), 200)


@application.get("/api/mempool/")
def api__mempool():
    try:
        the_mempool = cryptocurrency.getrawmempool(True)
    except JSONRPCException:
        return make_response(jsonify({'message': 'There was a JSON error. Try again later',
                                      'error': 'invalid'}), 422)
    else:
        return make_response(jsonify(the_mempool), 200)


@application.get("/api/rawtx/<transaction>/")
def api__rawtx(transaction):
    try:
        the_transaction = cryptocurrency.getrawtransaction(transaction, 1)
    except JSONRPCException:
        return make_response(jsonify({'message': 'This transaction is invalid',
                                      'error': 'invalid'}), 422)
    else:
        return make_response(jsonify(the_transaction), 200)


@application.get("/api/receivedbyaddress/<address>/")
def api__received_by_address(address):
    return make_response(jsonify({'message': 'todo',
                                  'error': 'todo'}), 200)


@application.get("/api/richlist/")
def api__rich_list():
    return make_response(jsonify({'message': 'todo',
                                  'error': 'todo'}), 200)


@application.get("/api/sentbyaddress/<address>/")
def api__sent_by_address(address):
    return make_response(jsonify({'message': 'todo',
                                  'error': 'todo'}), 200)


@application.get("/api/totalcoins/")
def api__total_coins():
    return make_response(jsonify({'message': float(cryptocurrency.gettxoutsetinfo()['total_amount']),
                                  'error': 'none'}), 200)


@application.get("/api/totaltransactions/")
def api__total_transactions():
    return make_response(jsonify({'message': cryptocurrency.gettxoutsetinfo()['transactions'],
                                  'error': 'none'}), 200)


@application.get("/api/validateaddress/<address>/")
def api__validate_address(address):
    if cryptocurrency.validateaddress(address)['isvalid']:
        return make_response(jsonify({'message': 'valid',
                                      'error': 'none'}), 200)
    else:
        return make_response(jsonify({'message': 'invalid',
                                      'error': 'this string cannot be verified as an address'}), 422)
