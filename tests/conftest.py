"""Isola serviços externos: nenhum teste envia WhatsApp, Pix ou grava em produção."""
import importlib
import os
import sys
from unittest.mock import MagicMock
import pytest

@pytest.fixture
def api(monkeypatch):
    for key in ('TWILIO_ACCOUNT_SID', 'TWILIO_AUTH_TOKEN', 'TWILIO_VERIFY_SERVICE_SID', 'TWILIO_WHATSAPP_SANDBOX_NUMBER'):
        monkeypatch.setenv(key, 'TEST_VALUE')
    monkeypatch.setenv('SUPABASE_URL', '')
    monkeypatch.setenv('SUPABASE_KEY', '')
    monkeypatch.setenv('MERCADOPAGO_ACCESS_TOKEN', '')
    # .env local não deve sobrescrever a configuração de testes.
    import dotenv
    monkeypatch.setattr(dotenv, 'load_dotenv', lambda *a, **kw: False)
    if 'app' in sys.modules:
        module = importlib.reload(sys.modules['app'])
    else:
        module = importlib.import_module('app')
    module.app.config.update(TESTING=True)
    monkeypatch.setattr(module, 'supabase', None)
    monkeypatch.setattr(module, 'sdk', None)
    return module

@pytest.fixture
def client(api):
    return api.app.test_client()

@pytest.fixture
def db(api, monkeypatch):
    fake = MagicMock()
    monkeypatch.setattr(api, 'supabase', fake)
    return fake
