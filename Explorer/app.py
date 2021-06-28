# ~/venv/bin/pip install Flask Flask-SQLALchemy Flask-WTF gunicorn psycopg2-binary python-bitcoinrpc Werkzeug
# apt install postgresql postgresql-client
# ----------------------------------------------
# Use Python 3.3+ because of `decimal` issues:
# https://docs.sqlalchemy.org/en/14/core/type_basics.html#sqlalchemy.types.Numeric
import importlib
import logging
import sys
from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException
from flask import Flask, jsonify, make_response, request
from flask import redirect, url_for, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFError, CSRFProtect
from sqlalchemy.sql import desc
from werkzeug.middleware.proxy_fix import ProxyFix
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length
from helpers import format_difficulty, format_transaction_length, format_time
from helpers import generate_front_page_blocks, generate_previous_and_next_block
from config import coin_name, rpcpassword, rpcport, rpcuser
from config import app_key, csrf_key, database_uri
from models import db
from models import Blocks

try:
    cryptocurrency = AuthServiceProxy(f"http://{rpcuser}:{rpcpassword}@127.0.0.1:{rpcport}")
except ValueError:
    print("One of these is wrong: rpcuser/rpcpassword/rpcport. Go into config.py and fix this.")
    sys.exit()

def create_app():
    application = Flask(__name__)
    application.debug = True
    application.logger.setLevel(logging.INFO)
    application.secret_key = app_key
    # check blockchain/README.md for this
    application.config['COIN_NAME'] = ''
    importlib.import_module('blockchain', application.config['COIN_NAME'].lower())
    application.config['MAX_CONTENT_LENGTH'] = 256
    application.config['PROGRAM_NAME'] = 'Cryptocurrency Explorer'
    application.config['SESSION_COOKIE_NAME'] = 'csrf_token'
    application.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    application.config['SQLALCHEMY_DATABASE_URI'] = database_uri
    application.config['VERSION'] = 0.7
    application.config['WTF_CSRF_SECRET_KEY'] = csrf_key
    application.jinja_env.trim_blocks = True
    application.jinja_env.lstrip_blocks = True
    # Set this when using HTTPS
    # app.config['SESSION_COOKIE_SECURE'] = True
    application.wsgi_app = ProxyFix(application.wsgi_app, x_proto=1, x_host=1)
    db.init_app(application)
    return application


application = create_app()
application.app_context().push()
csrf = CSRFProtect(application)


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


@application.route('/', methods=['GET', 'POST'])
def index():
    form = SearchForm(request.form)
    if request.method == 'POST' and form.validate_on_submit():
        try:
            if int(form.search.data) in range(0, cryptocurrency.getblockcount() + 1):
                return redirect(url_for('block', block_hash_or_height=int(form.search.data)))
        except ValueError:
            try:
                if cryptocurrency.getblock(form.search.data)['hash']:
                    return redirect(url_for('block', block_hash_or_height=form.search.data))
            except JSONRPCException:
                if cryptocurrency.validateaddress(form.search.data)['isvalid']:
                    return redirect(url_for('api__validate_address', address=form.search.data))
                else:
                    return make_response(jsonify({'message': 'todo',
                                                  'error': 'todo'}), 200)
    return render_template('index.html',
                           form=form,
                           front_page_blocks=generate_front_page_blocks(db),
                           format_time=format_time)


@application.route('/block/', methods=['GET'])
def redirect_to_block():
    return redirect(url_for('block', block_hash_or_height="0"))


@application.route('/block/<block_hash_or_height>/', methods=['GET'])
def block(block_hash_or_height):
    try:
        if int(block_hash_or_height) in range(0, cryptocurrency.getblockcount() + 1):
            block_raw_hash = cryptocurrency.getblockhash(int(block_hash_or_height))
            the_block = cryptocurrency.getblock(block_raw_hash)
            previous_block_hash, next_block_hash = generate_previous_and_next_block(cryptocurrency, the_block)
            value_out = 0
            for number, this_transaction in enumerate(the_block['tx']):
                # TODO - this needs pulled from blockchain/*.py
                # This is wrong, which is known.
                if the_block['height'] == 0:
                    genesis_transaction = "38db759b7839bab107e8bf1108c66e17ab7f7c4607f9a606577e4165d5cf40d6"
                    genesis_hex = "010000000100000000000000000000000000000000" \
                                  "00000000000000000000000000000000ffffffff0e" \
                                  "04e0c146540101062f503253482fffffffff0100e1" \
                                  "f505000000002321022fe5dce550c108cfe6f2b0be" \
                                  "d99f6f0f6fdcbbda124795d22cfd7204e249f4feac00000000"
                    raw_block_tx = cryptocurrency.decoderawtransaction(genesis_hex)
                else:
                    raw_block_tx = cryptocurrency.getrawtransaction(this_transaction, 1)
                value_out += sum([x['value'] for x in raw_block_tx['vout']])
            return render_template('block.html',
                                   the_block=the_block,
                                   previous_block_hash=previous_block_hash,
                                   next_block_hash=next_block_hash,
                                   format_time=format_time,
                                   format_difficulty=format_difficulty,
                                   format_transaction_length=format_transaction_length,
                                   value_out=value_out)
        else:
            return render_template('404.html', error="Not a valid block height/hash"), 404
    except ValueError:
        try:
            the_block = cryptocurrency.getblock(block_hash_or_height)
            previous_block_hash, next_block_hash = generate_previous_and_next_block(cryptocurrency, the_block)
            value_out = 0
            for number, this_transaction in enumerate(the_block['tx']):
                if the_block['height'] == 0:
                    # TODO - this needs pulled from blockchain/*.py
                    # This is wrong, which is known.
                    genesis_transaction = "38db759b7839bab107e8bf1108c66e17ab7f7c4607f9a606577e4165d5cf40d6"
                    genesis_hex = "010000000100000000000000000000000000000000" \
                                  "00000000000000000000000000000000ffffffff0e" \
                                  "04e0c146540101062f503253482fffffffff0100e1" \
                                  "f505000000002321022fe5dce550c108cfe6f2b0be" \
                                  "d99f6f0f6fdcbbda124795d22cfd7204e249f4feac00000000"
                    raw_block_tx = cryptocurrency.decoderawtransaction(genesis_hex)
                else:
                    raw_block_tx = cryptocurrency.getrawtransaction(this_transaction, 1)
                value_out += sum([x['value'] for x in raw_block_tx['vout']])
            return render_template('block.html',
                                   the_block=the_block,
                                   previous_block_hash=previous_block_hash,
                                   next_block_hash=next_block_hash,
                                   format_time=format_time,
                                   format_difficulty=format_difficulty,
                                   format_transaction_length=format_transaction_length,
                                   value_out=value_out)
        except JSONRPCException:
            return render_template('404.html', error="Not a valid block height/hash"), 404


@application.route('/api/', methods=['GET'])
def api_index():
    return render_template('api_index.html')


@application.route('/api/confirmations/', methods=['GET'])
def redirect_to_api__confirmations():
    return redirect(url_for('api__confirmations', userinput_block_height="0"))


@application.route('/api/validateaddress/', methods=['GET'])
def redirect_to_api__validate_address():
    return redirect(url_for('api__validate_address', address="INVALID_ADDRESS"))


@application.route('/api/blockcount/', methods=['GET'])
def api__block_count(db):
    return make_response(jsonify({'message': db.session.query(Blocks).order_by(desc('height')).first().height,
                                  'error': 'none'}), 200)


@application.route('/api/confirmations/<userinput_block_height>/', methods=['GET'])
def api__confirmations(userinput_block_height):
    try:
        userinput_block_height = int(userinput_block_height)
        latest_block = db.session.query(Blocks).order_by(desc('height')).first()
        latest_block_height = int(latest_block.height)
        latest_block_hash = latest_block.hash
        # check if this is a block number like 0 or something else.
        # +1 because range() goes up to but doesn't include the number, so to include it we do +1
        if userinput_block_height in range(0, latest_block_height + 1):
            userinput_block_hash = db.session.query(Blocks).filter_by(height=userinput_block_height).first().hash
            block_confirmations = (latest_block_height + 1) - userinput_block_height
            return make_response(jsonify({'confirmations': block_confirmations,
                                          'block_hash': userinput_block_hash,
                                          'block_height': userinput_block_height,
                                          'error': 'none'}), 200)
        else:
            return make_response(jsonify({'message': 'This block height is invalid',
                                          'error': 'invalid'}), 422)
    except ValueError:
        # not a block number, check if it's a hash
        try:
            userinput_block_hash = db.session.query(Blocks).filter_by(hash=userinput_block_height).first()
            userinput_block_height = int(userinput_block_hash.height)
            latest_block = db.session.query(Blocks).order_by(desc('height')).first()
            latest_block_height = int(latest_block.height)
            latest_block_hash = latest_block.hash
            block_confirmations = (latest_block_height + 1) - userinput_block_height
            return make_response(jsonify({'confirmations': block_confirmations,
                                          'block_hash': userinput_block_hash.hash,
                                          'block_height': userinput_block_height,
                                          'error': 'none'}), 200)
        except JSONRPCException:
            return make_response(jsonify({'message': 'Not a valid block height/hash',
                                          'error': 'invalid'}), 422)


@application.route('/api/richlist/', methods=['GET'])
def api__rich_list():
    return make_response(jsonify({'message': 'todo',
                                  'error': 'todo'}), 200)


@application.route('/api/totalcoins/', methods=['GET'])
def api__total_coins():
    return make_response(jsonify({'message': float(cryptocurrency.gettxoutsetinfo()['total_amount']),
                                  'error': 'none'}), 200)


@application.route('/api/totaltransactions/', methods=['GET'])
def api__total_transactions():
    return make_response(jsonify({'message': cryptocurrency.gettxoutsetinfo()['transactions'],
                                  'error': 'none'}), 200)


@application.route('/api/validateaddress/<address>/', methods=['GET'])
def api__validate_address(address):
    if cryptocurrency.validateaddress(address)['isvalid']:
        return make_response(jsonify({'message': 'valid',
                                      'error': 'none'}), 200)
    else:
        return make_response(jsonify({'message': 'invalid',
                                      'error': 'this string cannot be verified as an address'}), 422)