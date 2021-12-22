EMPTY = []
SUPPORTED_COINS = ['Bitcoin', 'Litecoin', 'Defcoin', 'Woodcoin']


class Bitcoin:
    unique = {'tx': {},
              'genesis': {'timestmap': 1231006505,
                          'hash': '000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f',
                          'prev_hash': '0000000000000000000000000000000000000000000000000000000000000000'}}


class Litecoin:
    unique = {'tx': {},
              'genesis': {'timestamp': 1317972665,
                          'hash': '12a765e31ffd4059bada1e25190f6e98c99d9714d334efa41a195a7e7e04bfe2',
                          'prev_hash': '0000000000000000000000000000000000000000000000000000000000000000'}}

class Defcoin:
    unique = {'tx': {},
              'genesis': {'timestamp': 1394002925,
                          'hash': '192047379f33ffd2bbbab3d53b9c4b9e9b72e48f888eadb3dcf57de95a6038ad',
                          'prev_hash': '0000000000000000000000000000000000000000000000000000000000000000'}}


class Woodcoin:
    # Woodcoin's initial transaction is empty
    unique = {'tx': {'d508b7916ec00595c1f8e1c767dc3b37392a5e68adf98118bca80a2ed58331d6': EMPTY},
              'genesis': {'timestamp': 1413817324,
                          'hash': '30758383eae55ae5c7752b73388c1c85bdfbe930ad25ad877252841ed1e734a4',
                          'prev_hash': '0000000000000000000000000000000000000000000000000000000000000000'}}
