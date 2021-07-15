Supported Setup
===============

Please be aware that the only supported setup
is listed below.

If you use anything other than these, you **WILL NOT** receive official support!:
- Nginx as HTTP server
- PostgreSQL as DB

How-To
======

Don't setup Nginx or Supervisor/Systemd, there
are other things that need done first.

- Go to the [blockchain README.md](Explorer/blockchain/README.md)
  and read it
- TODO


Venv
====

[ this part needs testing...]

For development, setting a virtualenv in the project root is recommended. The venv should be created in `.venv`.

A recent version of pipenv is required to setup the virtualenv - you can either install it with `--user` or manually create the venv and install it there.

You can then install required libraries with this command (`-d` also installs development libraries).

```sh
pipenv install [ -d ]
```

If you need requirements files you can create them with:

```sh
pipenv lock -r >requirements.txt
pipenv lock -d >dev-requirements.txt
```
When using Visual Studio Code, the virtualenv shoule get automatically activated.
