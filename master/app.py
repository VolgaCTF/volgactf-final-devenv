import os
import base64
import hashlib
import redis
import jwt
import datetime
from flask import Flask, request, render_template, jsonify
import requests
import pytz
import json
from flask_sse import sse
from collections import deque
from random import randrange
from random import choice
from string import ascii_letters, digits


app = Flask(__name__)
app.config['REDIS_URL'] = 'redis://redis:6379/2'
app.register_blueprint(sse, url_prefix='/stream')

cache = redis.Redis(host='redis', port=6379, db=1)


@app.route('/')
def index():
    return render_template('index.html')


def issue_flag():
    secret = base64.urlsafe_b64decode(
        os.getenv('THEMIS_FINALS_FLAG_GENERATOR_SECRET')
    )
    h = hashlib.md5()
    h.update(os.urandom(32))
    h.update(secret)
    flag = h.hexdigest()
    label = ''.join(choice(ascii_letters + digits) for _ in range(8))
    return flag, label


def create_capsule(flag):
    key = os.getenv('THEMIS_FINALS_FLAG_SIGN_KEY_PRIVATE').replace('\\n', '\n')
    return '{0}{1}{2}'.format(
        os.getenv('THEMIS_FINALS_FLAG_WRAP_PREFIX'),
        jwt.encode(
            {'flag': flag},
            key=key,
            algorithm='ES256'
        ).decode('ascii'),
        os.getenv('THEMIS_FINALS_FLAG_WRAP_SUFFIX')
    )


def create_push_job(capsule, label, params):
    return {
        'params': {
            'endpoint': params.get('endpoint', '127.0.0.1'),
            'capsule': capsule,
            'label': label
        },
        'metadata': {
            'timestamp': datetime.datetime.now(pytz.utc).isoformat(),
            'round': int(params.get('round', '1')),
            'team_name': params.get('team', 'Team'),
            'service_name': params.get('service', 'Service')
        },
        'report_url': 'http://master/api/checker/v2/report_push'
    }


def create_pull_job(capsule, label, params):
    return {
        'params': {
            'request_id': randrange(1, 100),
            'endpoint': params['endpoint'],
            'capsule': capsule,
            'label': label
        },
        'metadata': {
            'timestamp': datetime.datetime.now(pytz.utc).isoformat(),
            'round': params['round'],
            'team_name': params['team'],
            'service_name': params['service']
        },
        'report_url': 'http://master/api/checker/v2/report_pull'
    }


@app.route('/push', methods=['POST'])
def push():
    flag, label = issue_flag()
    capsule = create_capsule(flag)
    job = create_push_job(capsule, label, request.form)
    auth = (os.getenv('THEMIS_FINALS_AUTH_CHECKER_USERNAME'),
            os.getenv('THEMIS_FINALS_AUTH_CHECKER_PASSWORD'))
    checker_host = request.form.get('checker', 'checker')
    url = 'http://{0}/push'.format(checker_host)
    r = requests.post(url, json=job, auth=auth)
    update_logs(dict(
        type='outcoming',
        category='PUSH',
        timestamp=datetime.datetime.now(pytz.utc).isoformat(),
        raw=job
    ))
    sse.publish(get_logs(), type='logs')
    update_flags(dict(
        checker_host=checker_host,
        flag=flag,
        status=-1,
        capsule=capsule,
        label=label,
        params=dict(
            endpoint=request.form.get('endpoint', '127.0.0.1'),
            round=int(request.form.get('round', '1')),
            team=request.form.get('team', 'Team'),
            service=request.form.get('service', 'Service')
        )
    ))
    sse.publish(get_flags(), type='flags')
    return jsonify(job), r.status_code


@app.route('/pull', methods=['POST'])
def pull():
    flag = request.form.get('flag')
    app.logger.info(flag)
    flags = get_flags()
    for x in flags:
        app.logger.info(x['flag'])
    item = [x for x in flags if x['flag'] == flag][0]
    job = create_pull_job(item['capsule'], item['label'], item['params'])
    auth = (os.getenv('THEMIS_FINALS_AUTH_CHECKER_USERNAME'),
            os.getenv('THEMIS_FINALS_AUTH_CHECKER_PASSWORD'))
    checker_host = item['checker_host']
    url = 'http://{0}/pull'.format(checker_host)
    r = requests.post(url, json=job, auth=auth)
    update_logs(dict(
        type='outcoming',
        category='PULL',
        timestamp=datetime.datetime.now(pytz.utc).isoformat(),
        raw=job
    ))
    sse.publish(get_logs(), type='logs')
    return jsonify(job), r.status_code


def get_logs():
    logs_str = cache.get('themis_finals_logs')
    if logs_str is None:
        return list()
    return json.loads(logs_str.decode('utf-8'))


def get_flags():
    flags_str = cache.get('themis_finals_flags')
    if flags_str is None:
        return list()
    return json.loads(flags_str.decode('utf-8'))


def update_logs(item):
    logs = deque(get_logs(), 25)
    logs.appendleft(item)
    cache.set('themis_finals_logs', json.dumps(list(logs)))


def update_flags(item):
    flags = deque(get_flags(), 25)
    flags.appendleft(item)
    cache.set('themis_finals_flags', json.dumps(list(flags)))


@app.route('/logs')
def logs():
    logs = get_logs()
    return jsonify(logs)


@app.route('/logs', methods=['DELETE'])
def clear_logs():
    cache.delete('themis_finals_logs')
    sse.publish(get_logs(), type='logs')
    return '', 204


@app.route('/flags')
def flags():
    flags = get_flags()
    return jsonify(flags)


@app.route('/flags', methods=['DELETE'])
def clear_flags():
    cache.delete('themis_finals_flags')
    sse.publish(get_flags(), type='flags')
    return '', 204


def edit_flags(flag, label, status):
    flags = get_flags()
    item = [x for x in flags if x['flag'] == flag][0]
    item['status'] = status
    item['label'] = label
    cache.set('themis_finals_flags', json.dumps(flags))


@app.route('/api/checker/v2/report_push', methods=['POST'])
def report_push():
    data = request.get_json()
    update_logs(dict(
        type='incoming',
        category='PUSH',
        timestamp=datetime.datetime.now(pytz.utc).isoformat(),
        raw=data
    ))
    sse.publish(get_logs(), type='logs')
    if data['status'] == 101:
        edit_flags(data['flag'], data['label'], data['status'])
        sse.publish(get_flags(), type='flags')
    return '', 204


@app.route('/api/checker/v2/report_pull', methods=['POST'])
def report_pull():
    data = request.get_json()
    update_logs(dict(
        type='incoming',
        category='PULL',
        timestamp=datetime.datetime.now(pytz.utc).isoformat(),
        raw=data
    ))
    sse.publish(get_logs(), type='logs')
    return '', 204
