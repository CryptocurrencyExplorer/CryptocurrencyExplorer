import datetime
import decimal
import json
import requests


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
