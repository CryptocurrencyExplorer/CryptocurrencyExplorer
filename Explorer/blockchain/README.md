# What is this?

This folder contains individual files for
supported coins, tokens, and other things that run on a blockchain.

Besides the above, within the individual files contain information
specific about each. Such as, Woodcoin's blank genesis transaction.

# Why am I being redirected here from app.py?

``app.config['COIN_NAME']`` requires a valid filename reference
from anything supported in the blockchain folder.

This ensures specifics of the coin/token/etc are taken
into account.

The casing *shouldn't* matter as `importlib.import_module('blockchain', app.config['COIN_NAME'].lower())`
is occuring in app.py - just make sure the filename exists.

`app.config['COIN_NAME']` is also used within templates, so spelling out
something like `Bitcoin` or `CryptocurrencyExplorerCoin` is fine
if `app.config['COIN_NAME']` is properly referencing a file in the
blockchain folder.

Using a name that doesn't exist will probably mess something
up. It also hasn't been tested and probably won't be.

# Adding new coins/tokens/etc

### Filenames
- All filenames within the blockchain file are lowercase.
- If a coin ( "CryptocurrencyExplorerCoin" ) is forked
  ( "CryptocurrencyExplorerCoin 2" ), that forked version's filename
  within /blockchain and thus ``app.config['COIN_NAME']`` should have
  the space replaced with a dash ( cryptocurrencyexplorercoin-2.py ) .

### File formatting

- TODO