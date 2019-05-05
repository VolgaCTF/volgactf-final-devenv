from ecdsa import SigningKey, NIST256p
from random import choice
from string import ascii_letters, digits
from io import open
from os import urandom
from base64 import urlsafe_b64encode


def get_random_str(size=16):
    return ''.join(choice(ascii_letters + digits) for _ in range(size))


def main():
    with open('volgactf-final-auth.env', 'w', encoding='utf-8') as f1:
        master_pwd = get_random_str()
        checker_pwd = get_random_str()
        template1 = (
            'THEMIS_FINALS_AUTH_MASTER_USERNAME={0}\n'
            'THEMIS_FINALS_AUTH_MASTER_PASSWORD={1}\n'
            'THEMIS_FINALS_AUTH_CHECKER_USERNAME={2}\n'
            'THEMIS_FINALS_AUTH_CHECKER_PASSWORD={3}'
        ).format(
            'master',
            master_pwd,
            'checker',
            checker_pwd
        )
        f1.write(template1)

    private_key = SigningKey.generate(curve=NIST256p)
    public_key = private_key.get_verifying_key()

    with open('volgactf-final-public.env', 'w', encoding='utf-8') as f2:
        template2 = (
            'THEMIS_FINALS_FLAG_SIGN_KEY_PUBLIC={0}\n'
            'THEMIS_FINALS_FLAG_WRAP_PREFIX={1}\n'
            'THEMIS_FINALS_FLAG_WRAP_SUFFIX={2}'
        ).format(
            public_key.to_pem().decode('ascii').strip().replace('\n', '\\n'),
            'VolgaCTF{',
            '}'
        )
        f2.write(template2)

    secret = urlsafe_b64encode(urandom(32)).decode('ascii')

    with open('volgactf-final-private.env', 'w', encoding='utf-8') as f3:
        template3 = (
            'THEMIS_FINALS_FLAG_SIGN_KEY_PRIVATE={0}\n'
            'THEMIS_FINALS_FLAG_GENERATOR_SECRET={1}'
        ).format(
            private_key.to_pem().decode('ascii').strip().replace('\n', '\\n'),
            secret
        )
        f3.write(template3)


if __name__ == '__main__':
    main()
