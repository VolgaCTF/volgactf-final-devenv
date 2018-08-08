FROM python:3.6-alpine
ADD . /code
WORKDIR /code
RUN apk add --update build-base libffi-dev openssl-dev && pip install aiohttp PyJWT cryptography python-dateutil themis.finals.checker.result
CMD ["python", "-u", "server.py"]
