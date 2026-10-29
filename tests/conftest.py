import os

# Se configuran antes de importar app; nunca se carga el .env del usuario.
os.environ['PYTHON_DOTENV_DISABLED'] = '1'
os.environ.pop('DB_HOST', None)
os.environ['DATABASE_URL'] = 'sqlite://'
os.environ.pop('GROQ_API_KEY', None)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app import main, auth
from app.database import Base, get_db
from app.services import groq


@pytest.fixture
def db():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        yield session
    engine.dispose()


@pytest.fixture
def client(db, monkeypatch):
    def override_db():
        yield db
    main.app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(main, 'engine', db.get_bind())
    monkeypatch.setattr(groq, 'client', None)
    with TestClient(main.app) as client:
        yield client
    main.app.dependency_overrides.clear()


@pytest.fixture
def headers(entra_token):
    return {'Authorization': 'Bearer ' + entra_token()}


@pytest.fixture(autouse=True)
def sin_servicios_externos(monkeypatch):
    import socket
    for nombre in ('COMMUNICATIONS_REAL_ENABLED', 'TWILIO_ACCOUNT_SID', 'TWILIO_AUTH_TOKEN', 'TWILIO_PHONE_NUMBER',
                   'TWILIO_WHATSAPP_NUMBER', 'SENDGRID_API_KEY', 'SENDGRID_FROM_EMAIL', 'SENDGRID_FROM_NAME',
                   'GROQ_SMS_MODEL', 'TWILIO_STATUS_CALLBACK_URL'):
        monkeypatch.delenv(nombre, raising=False)
    def bloquear(*args, **kwargs):
        raise AssertionError('Red externa prohibida durante pytest')
    monkeypatch.setattr(socket.socket, 'connect', bloquear)
    monkeypatch.setattr(socket.socket, 'connect_ex', bloquear)
    monkeypatch.setattr(socket, 'create_connection', bloquear)


@pytest.fixture(scope='session')
def rsa_key():
    from cryptography.hazmat.primitives.asymmetric import rsa
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(autouse=True)
def entra_config(monkeypatch, rsa_key):
    import json
    import jwt
    tenant = '11111111-1111-4111-8111-111111111111'
    client_id = '22222222-2222-4222-8222-222222222222'
    monkeypatch.setenv('ENTRA_TENANT_ID', tenant)
    monkeypatch.setenv('ENTRA_CLIENT_ID', client_id)
    monkeypatch.setenv('ENTRA_REQUIRED_SCOPE', 'access_as_user')
    issuer = f'https://login.microsoftonline.com/{tenant}/v2.0'
    key = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(rsa_key.public_key()))
    key.update(kid='test-key', use='sig', alg='RS256', issuer=issuer)
    def discovery(url):
        if url.endswith('/.well-known/openid-configuration'):
            return {'issuer': issuer, 'jwks_uri': f'https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys'}
        return {'keys': [key]}
    monkeypatch.setattr(auth, 'descargar_json', discovery)
    monkeypatch.setattr(auth, 'claves', auth.ClavesEntra())
    return tenant, client_id, issuer, key


@pytest.fixture
def entra_token(rsa_key, entra_config):
    import time
    import jwt
    tenant, client_id, issuer, _ = entra_config
    def crear(overrides=None, key=None, kid='test-key'):
        now = int(time.time())
        claims = {'iss': issuer, 'aud': client_id, 'tid': tenant, 'ver': '2.0',
                  'oid': '33333333-3333-4333-8333-333333333333', 'name': 'Usuario Microsoft',
                  'preferred_username': 'prueba@example.com', 'scp': 'access_as_user',
                  'iat': now, 'nbf': now - 1, 'exp': now + 600}
        claims.update(overrides or {})
        return jwt.encode(claims, key or rsa_key, algorithm='RS256', headers={'kid': kid})
    return crear
