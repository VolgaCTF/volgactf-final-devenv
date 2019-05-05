# VolgaCTF Final devenv

A platform to develop & test an A/D CTF service and its checker.

## Prerequisites
- *nix compatible system
- [Docker Compose](https://docs.docker.com/compose/)
- Python 3

## A general outlook
This repository contains a docker-compose configuration for several containers, namely `redis`, `master`, `checker` and `service`, which provide a development and testing environment.

## Network
`master` must be able to communicate with `redis` and `checker` containers.  
`checker` must be able to communicate with `master` and `service` containers.

## Setup
```
$ pip3 install ecdsa && python3 env_vars.py
$ cp docker-compose.example.yml docker-compose.yml
```

The commands above generate a few secrets (for flag signing) as well as create a `docker-compose.yml` file from a sample. This file may require further customization (see [Development](#development) section).

## Running
```
$ docker-compose up
```

Run containers in foreground (add `-d` flag to run in background). One may need to launch any `docker-compose` command as a superuser.

## Usage
Provided that everything is installed correctly, a dashboard is available on `http://127.0.0.1:8000`. ![dashboard](screenshot.png "VolgaCTF Final devenv")

The form on the left helps specify `PUSH` operation parameters. Note that `Checker` and `Endpoint` fields stand for a checker and a service container hostnames or IP addresses, so that other checkers and/or services may be used, regardless of whether they belong to the very docker-compose deployment or not.

The section in the middle is populated with all pushed flags so that a `PULL` operation may be initiated. Note that `PULL` button is active only when an antecedent `PUSH` operation was successful.

Detailed logs comprise the section on the right.

## Development
To develop & test a service along with a checker, `service` and `checker` sections in `docker-compose.yml` should be modified accordingly:

*docker-compose.yml*
```yaml
  ...
  checker:
    # image: 'volgactf/volgactf-final-devenv-checker:1.0.0'
    image: 'awesome/awesome-checker:1.0.0'

  service:
    # image: 'volgactf/volgactf-final-devenv-service:1.0.0'
    image: 'awesome/awesome-service:1.0.0'
  ...
```

## See also

1. [master image source](https://github.com/VolgaCTF/volgactf-final-devenv-master)
2. [service image source](https://github.com/VolgaCTF/volgactf-final-devenv-service)
3. [checker image source](https://github.com/VolgaCTF/volgactf-final-devenv-checker)
4. [checker protocol](https://github.com/VolgaCTF/volgactf-final-checker-protocol)

## License
MIT @ [VolgaCTF](https://github.com/VolgaCTF)
