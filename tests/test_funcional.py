"""Casos de caixa-preta gerados a partir dos endpoints e contratos observáveis."""
import pytest

@pytest.mark.parametrize('categoria,valor,esperado', [
    ('Progressiva', 240, 120),
    ('Mechas', 300, 150),
    ('Corte', 80, 80),
])
def test_pix_valor_conforme_categoria(client, categoria, valor, esperado):
    resp = client.post('/api/agendamentos/gerar-pix-sinal', json={
        'categoria_servico': categoria, 'valor_total': valor,
        'cliente_nome': 'Cliente Teste', 'servico_nome': categoria,
    })
    assert resp.status_code == 201
    body = resp.get_json()
    assert body['valor_pago'] == esperado
    assert body['exige_sinal'] == (categoria != 'Corte')
    assert body['payment_id'].startswith('SIMULADO_')


def test_agendamento_simulado_sem_banco(client):
    resp = client.post('/api/agendamentos', json={
        'salao_id': 'salao-teste', 'profissional_id': 'prof-teste',
        'servico_id': 'serv-teste', 'exige_sinal': True,
        'data_hora_inicio': '2026-11-10T10:00:00',
    })
    assert resp.status_code == 201
    assert resp.get_json()['agendamento']['status'] == 'pendente_sinal'
    assert resp.get_json()['agendamento']['status_pagamento'] == 'aguardando_pix'


def test_webhook_evento_irrelevante_retorna_ok(client):
    resp = client.post('/api/webhooks/mercadopago', json={'type': 'other'})
    assert resp.status_code == 200
    assert resp.get_json() == {'status': 'ok'}
