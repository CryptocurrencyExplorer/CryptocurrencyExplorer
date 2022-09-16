# Autodetection
autodetect_config = True
autodetect_tables = True

# Coin specific
coin_name = "CryptocurrencyExplorerCoin"
rpcpassword = None
rpcport = None
rpcuser = None

# Flask specific
app_key = r"""app_key"""
csrf_key = "csrf_key"
database_uri = "postgresql://postgres:db_password@localhost/db"
program_name = "Cryptocurrency Explorer"

# For a randomized app_key or csrf_key, you can use the following:
# import secrets
# a = "€‚ƒ„…†‡ˆ‰Š‹ŒŽ‘’“”•–—˜™š›œžŸ¡¢£¤¥¦§¨©ª«¬®¯°±º¹²³´µ¶"
# b = "·¸»¼½¾¿ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖ×ØÙÚÛÜÝÞßàáâãäåæçèéê"
# c = "ëìíîïðñòóôõö÷øùúûüýþÿ0123456789abcdefghijklmnopqrs"
# d = "tuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ!\"#$%&\'()*+,-./"
# e = ":;<=>?@[\\]^_`{|}~"
# alphabet = a + b + c + d + e
# multiplier = secrets.choice(range(1, 16))
# the_length = 64 * multiplier
# new = [secrets.choice(alphabet) for x in range(1, the_length)]
# print(''.join(new))
