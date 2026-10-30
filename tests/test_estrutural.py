"""Testes da comunicação Flask ↔ Supabase ↔ Mercado Pago (com mocks)."""
from types import SimpleNamespace
from unittest.mock import MagicMock


def test_agendamento_cria_cliente_e_reserva(client, db):
    clientes = MagicMock()
    agendamentos = MagicMock()
    db.table.side_effect = lambda name: {'clientes': clientes, 'agendamentos': agendamentos}[name]
    clientes.select.return_value.eq.return_value.eq.return_value.execute.return_value = SimpleNamespace(data=[])
    clientes.insert.return_value.execute.return_value = SimpleNamespace(data=[{'id': 'cliente-novo'}])
    agendamentos.insert.return_value.execute.return_value = SimpleNamespace(data=[{'id': 'ag-1', 'status': 'pendente_sinal'}])
    resp = client.post('/api/agendamentos', json={
        'salao_id': 's-1', 'profissional_id': 'p-1', 'servico_id': 'sv-1',
        'cliente_nome': 'Teste', 'cliente_whatsapp': '32999999999', 'exige_sinal': True,
    })
    assert resp.status_code == 201
    payload = agendamentos.insert.call_args.args[0]
    assert payload['cliente_id'] == 'cliente-novo'
    assert payload['status'] == 'pendente_sinal'
    assert payload['status_pagamento'] == 'aguardando_pix'


def test_agendamento_reutiliza_cliente_existente(client, db):
    clientes = MagicMock()
    agendamentos = MagicMock()
    db.table.side_effect = lambda name: {'clientes': clientes, 'agendamentos': agendamentos}[name]
    clientes.select.return_value.eq.return_value.eq.return_value.execute.return_value = SimpleNamespace(data=[{'id': 'cliente-existente'}])
    agendamentos.insert.return_value.execute.return_value = SimpleNamespace(data=[{'id': 'ag-2'}])
    resp = client.post('/api/agendamentos', json={
        'salao_id': 's-1', 'cliente_nome': 'Teste', 'cliente_whatsapp': '32999999999',
    })
    assert resp.status_code == 201
    clientes.insert.assert_not_called()
    assert agendamentos.insert.call_args.args[0]['cliente_id'] == 'cliente-existente'


def test_webhook_pagamento_aprovado_atualiza_agendamento(client, api, db, monkeypatch):
    sdk = MagicMock()
    sdk.payment.return_value.get.return_value = {'response': {'status': 'approved'}}
    monkeypatch.setattr(api, 'sdk', sdk)
    resp = client.post('/api/webhooks/mercadopago', json={
        'type': 'payment', 'data': {'id': 12345},
    })
    assert resp.status_code == 200
    table = db.table.return_value
    table.update.assert_called_once_with({'status': 'agendado', 'status_pagamento': 'sinal_pago'})
    table.update.return_value.eq.assert_called_once_with('mercadopago_id', '12345')


def test_webhook_pagamento_pendente_nao_atualiza(client, api, db, monkeypatch):
    sdk = MagicMock()
    sdk.payment.return_value.get.return_value = {'response': {'status': 'pending'}}
    monkeypatch.setattr(api, 'sdk', sdk)
    resp = client.post('/api/webhooks/mercadopago', json={
        'type': 'payment', 'data': {'id': 987},
    })
    assert resp.status_code == 200
    db.table.assert_not_called()
