# What is this?

This folder contains individual files for
supported coins, tokens, and other things that run on a blockchain.

Besides the above, within the individual files contain information
specific about each. Such as, Woodcoin's blank genesis transaction.

# Why am I being redirected here from app.py?

``coin_name`` in config.py requires a valid filename reference
from anything supported in the blockchain folder.

This ensures specifics of the coin/token/etc are taken
into account.

The casing doesn't matter as `coin_name.capitalize()`
is occuring in app.py - just make sure the class exists in ``blockchain/__init__.py``.

---

`.config['COIN_NAME']` is also used within templates, so spelling out
something like `Bitcoin` or `CryptocurrencyExplorerCoin` is fine

if `.config['COIN_NAME']` is properly referencing a file in the
blockchain folder.

---

Using a name that doesn't exist might mess something up, and has been
prevented via a sys.exit().

Lacking a name hasn't been tested fully and not setting this will probably break something.

# Adding new coins/tokens/etc

### Filenames
- All filenames within the blockchain file are capitalized.
- Coins with spaces in them has't been tested.. <!-- TODO -->

### File formatting
<!-- TODO -->