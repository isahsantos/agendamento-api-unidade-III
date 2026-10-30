import os
import re
import mercadopago
from flask import Flask, request, jsonify, make_response, abort, Response
from flask_cors import CORS
from supabase import create_client, Client
from dotenv import load_dotenv
from icalendar import Calendar, Event
from datetime import datetime
import random
from datetime import datetime, timedelta, timezone
from twilio.rest import Client as TwilioClient
from twilio.base.exceptions import TwilioRestException


# ─── CONFIGURAÇÃO INICIAL ──────────────────────────────────────────────────────
load_dotenv()

app = Flask(__name__)

# Permite acesso CORS total de qualquer origem
CORS(app, resources={r"/*": {"origins": "*"}})


# --- Configuração da Twilio ---
twilio_client = TwilioClient(
    os.environ['TWILIO_ACCOUNT_SID'],
    os.environ['TWILIO_AUTH_TOKEN'],
)
VERIFY_SERVICE_SID = os.environ['TWILIO_VERIFY_SERVICE_SID']


# ─── INTERCEPTADOR PRE-FLIGHT (OPTIONS) ───────────────────────────────────────
@app.before_request
def handle_preflight():
    """Garante resposta imediata 200 OK para chamadas OPTIONS da Vercel."""
    if request.method == "OPTIONS":
        response = make_response()
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type, Authorization, Accept, Sec-Fetch-Mode")
        response.headers.add("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        return response, 200


# ─── CONEXÃO SUPABASE E MERCADO PAGO ──────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

MP_ACCESS_TOKEN = os.getenv("MERCADOPAGO_ACCESS_TOKEN", "")
sdk = mercadopago.SDK(MP_ACCESS_TOKEN) if MP_ACCESS_TOKEN else None

SERVICOS_COM_SINAL = ['Química', 'Mechas', 'Progressiva', 'Selagem', 'Balayage']


# ─── HEALTH CHECK ─────────────────────────────────────────────────────────────
@app.route('/', methods=['GET'])
@app.route('/api', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'online',
        'mensagem': 'API AgendaFácil rodando perfeitamente na Vercel!'
    }), 200


# ─── ROTAS DO SALÃO & BAIRROS ──────────────────────────────────────────────────
@app.route('/salao/<salao_id>/servicos', methods=['GET'])
@app.route('/api/salao/<salao_id>/servicos', methods=['GET'])
def get_servicos_salao(salao_id):
    try:
        if not supabase:
            return jsonify({'error': 'Supabase não configurado no backend.'}), 500

        res = supabase.table('servicos') \
            .select('*') \
            .eq('salao_id', salao_id) \
            .eq('ativo', True) \
            .execute()
        return jsonify(res.data), 200
    except Exception as e:
        return jsonify({'error': f'Erro ao buscar serviços: {str(e)}'}), 400


@app.route('/salao/<salao_id>/bairros-atendidos', methods=['GET'])
@app.route('/api/salao/<salao_id>/bairros-atendidos', methods=['GET'])
def get_bairros_atendidos(salao_id):
    try:
        if not supabase:
            return jsonify({'error': 'Supabase não configurado no backend.'}), 500

        res = supabase.table('taxa_deslocamento_bairros') \
            .select('id, bairro, taxa') \
            .eq('salao_id', salao_id) \
            .eq('ativo', True) \
            .order('bairro') \
            .execute()
        return jsonify(res.data), 200
    except Exception as e:
        return jsonify({'error': f'Erro ao buscar bairros: {str(e)}'}), 400


# ─── AUTENTICAÇÃO WHATSAPP / OTP (via Twilio Verify) ──────────────────────────

def formatar_e164_brasil(telefone: str) -> str:
    """
    Converte um telefone brasileiro em qualquer formato (com máscara,
    espaços, etc.) para o padrão E.164 exigido pela Twilio: +55DDDNUMERO
    """
    digitos = re.sub(r'\D', '', telefone)

    # Remove um "0" de discagem à frente, se vier por engano (ex: 031...)
    if digitos.startswith('0'):
        digitos = digitos[1:]

    # Já vem com código do país (55 + DDD + número = 12 ou 13 dígitos)
    if digitos.startswith('55') and len(digitos) in (12, 13):
        return f'+{digitos}'

    # Vem só com DDD + número (10 ou 11 dígitos)
    if len(digitos) in (10, 11):
        return f'+55{digitos}'

    raise ValueError(f'Número de telefone em formato inválido: {telefone}')




# --- Configuração da Twilio (envio manual via Sandbox) ---
twilio_client = TwilioClient(
    os.environ['TWILIO_ACCOUNT_SID'],
    os.environ['TWILIO_AUTH_TOKEN'],
)
TWILIO_WHATSAPP_SANDBOX_NUMBER = os.environ['TWILIO_WHATSAPP_SANDBOX_NUMBER']  # ex: 'whatsapp:+14155238886'

CODIGO_VALIDADE_MINUTOS = 5
COOLDOWN_REENVIO_SEGUNDOS = 60
MAX_TENTATIVAS_VALIDACAO = 5


def formatar_e164_brasil(telefone: str) -> str:
    digitos = re.sub(r'\D', '', telefone)
    if digitos.startswith('0'):
        digitos = digitos[1:]
    if digitos.startswith('55') and len(digitos) in (12, 13):
        return f'+{digitos}'
    if len(digitos) in (10, 11):
        return f'+55{digitos}'
    raise ValueError(f'Número de telefone em formato inválido: {telefone}')


@app.route('/auth/enviar-codigo', methods=['POST', 'OPTIONS'])
@app.route('/api/auth/enviar-codigo', methods=['POST', 'OPTIONS'])
def enviar_codigo():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    if not supabase:
        return jsonify({'error': 'Supabase não configurado no backend.'}), 500

    dados = request.get_json(silent=True) or {}
    telefone_bruto = dados.get('whatsapp', '')

    if not telefone_bruto:
        return jsonify({'error': 'Informe o número de WhatsApp.'}), 400

    try:
        telefone_e164 = formatar_e164_brasil(telefone_bruto)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    # Cooldown: evita reenvio em spam (e gasto à toa)
    agora = datetime.now(timezone.utc)
    ultimo = (
        supabase.table('otp_codigos')
        .select('criado_em')
        .eq('whatsapp', telefone_e164)
        .order('criado_em', desc=True)
        .limit(1)
        .execute()
    )
    if ultimo.data:
        criado_em = datetime.fromisoformat(ultimo.data[0]['criado_em'])
        segundos_passados = (agora - criado_em).total_seconds()
        if segundos_passados < COOLDOWN_REENVIO_SEGUNDOS:
            espera = int(COOLDOWN_REENVIO_SEGUNDOS - segundos_passados)
            return jsonify({'error': f'Aguarde {espera}s antes de solicitar um novo código.'}), 429

    codigo = f'{random.randint(0, 9999):04d}'
    expira_em = agora + timedelta(minutes=CODIGO_VALIDADE_MINUTOS)

    supabase.table('otp_codigos').insert({
        'whatsapp': telefone_e164,
        'codigo': codigo,
        'expira_em': expira_em.isoformat(),
    }).execute()

    try:
        twilio_client.messages.create(
            from_=TWILIO_WHATSAPP_SANDBOX_NUMBER,
            to=f'whatsapp:{telefone_e164}',
            body=(
                f'Seu código de verificação Studio Bella é: {codigo}\n\n'
                f'Válido por {CODIGO_VALIDADE_MINUTOS} minutos. Não compartilhe com ninguém.'
            ),
        )
        return jsonify({'status': 'pending'}), 200

    except TwilioRestException as e:
        app.logger.warning(f'Erro Twilio ao enviar código: {e}')

        # Código 63016/63018: número não fez o "join" no Sandbox
        if e.code in (63016, 63018):
            mensagem = (
                'Este número ainda não está autorizado a receber mensagens de teste. '
                'É necessário enviar a palavra de ativação do Sandbox pelo WhatsApp primeiro.'
            )
        else:
            mensagem = 'Não foi possível enviar o código. Tente novamente.'

        return jsonify({'error': mensagem}), 400


@app.route('/auth/verificar-codigo', methods=['POST', 'OPTIONS'])
@app.route('/api/auth/verificar-codigo', methods=['POST', 'OPTIONS'])
def verificar_codigo():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    if not supabase:
        return jsonify({'error': 'Supabase não configurado no backend.'}), 500

    dados = request.get_json(silent=True) or {}
    telefone_bruto = dados.get('whatsapp', '')
    codigo_informado = dados.get('codigo', '')

    if not telefone_bruto or not codigo_informado:
        return jsonify({'error': 'Informe o telefone e o código.'}), 400

    try:
        telefone_e164 = formatar_e164_brasil(telefone_bruto)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    registro = (
        supabase.table('otp_codigos')
        .select('*')
        .eq('whatsapp', telefone_e164)
        .eq('usado', False)
        .order('criado_em', desc=True)
        .limit(1)
        .execute()
    )

    if not registro.data:
        return jsonify({'error': 'Nenhum código pendente. Solicite um novo.'}), 400

    otp = registro.data[0]
    agora = datetime.now(timezone.utc)
    expira_em = datetime.fromisoformat(otp['expira_em'])

    if agora > expira_em:
        return jsonify({'error': 'Código expirado. Solicite um novo.'}), 400

    if otp['tentativas'] >= MAX_TENTATIVAS_VALIDACAO:
        return jsonify({'error': 'Máximo de tentativas excedido. Solicite um novo código.'}), 400

    if otp['codigo'] != codigo_informado:
        supabase.table('otp_codigos').update({
            'tentativas': otp['tentativas'] + 1,
        }).eq('id', otp['id']).execute()
        return jsonify({'error': 'Código incorreto.'}), 400

    supabase.table('otp_codigos').update({'usado': True}).eq('id', otp['id']).execute()
    return jsonify({'status': 'approved'}), 200


# ─── CALENDÁRIO DA PROFISSIONAL (FEED ICS) ────────────────────────────────────
@app.route('/profissional/<token>/calendario.ics')
def calendario_profissional(token):
    """
    Feed de calendário assinável (formato iCalendar).
    A profissional adiciona esta URL uma única vez no app de calendário
    dela (Google Calendar, Apple Calendar ou Outlook) e os agendamentos
    aparecem automaticamente, sem precisar clicar em nada a cada reserva.
    """
    if not supabase:
        abort(500, 'Supabase não configurado no backend.')

    profissional_resp = (
        supabase.table('profissionais')
        .select('id, nome')
        .eq('calendar_token', token)
        .maybe_single()
        .execute()
    )

    if not profissional_resp.data:
        abort(404, 'Link de calendário inválido.')

    profissional = profissional_resp.data

    agendamentos_resp = (
        supabase.table('agendamentos')
        .select('*')
        .eq('profissional_id', profissional['id'])
        .in_('status', ['confirmado', 'pendente'])
        .execute()
    )

    cal = Calendar()
    cal.add('prodid', '-//Studio Bella//Agenda Profissional//PT')
    cal.add('version', '2.0')
    cal.add('X-WR-CALNAME', f"Agenda — {profissional['nome']}")
    cal.add('X-PUBLISHED-TTL', 'PT15M')  # sugere ao app atualizar a cada 15min

    for ag in agendamentos_resp.data:
        event = Event()
        event.add('uid', f"agendamento-{ag['id']}@studiobella.app")
        event.add('summary', f"{ag.get('servico_nome', 'Atendimento')} — {ag['cliente_nome']}")
        event.add('dtstart', datetime.fromisoformat(ag['data_hora_inicio']))
        event.add('dtend', datetime.fromisoformat(ag['data_hora_fim']))

        descricao = [
            f"Cliente: {ag['cliente_nome']}",
            f"WhatsApp: {ag['cliente_whatsapp']}",
        ]
        if ag.get('endereco_rua'):
            descricao.append(
                f"Endereço: {ag['endereco_rua']}, {ag['endereco_numero']} — {ag.get('endereco_bairro', '')}"
            )
        if ag.get('fotos_avaliacao_urls'):
            descricao.append(f"Fotos para avaliação: {', '.join(ag['fotos_avaliacao_urls'])}")
        if ag.get('status') == 'pendente':
            descricao.append('⚠️ Sinal ainda não confirmado.')

        event.add('description', '\n'.join(descricao))
        if ag.get('endereco_bairro'):
            event.add('location', ag['endereco_bairro'])
        event.add('status', 'CONFIRMED' if ag['status'] == 'confirmado' else 'TENTATIVE')

        cal.add_component(event)

    return Response(
        cal.to_ical(),
        mimetype='text/calendar',
        headers={'Content-Type': 'text/calendar; charset=utf-8'},
    )


# ─── GERAR PIX DE 50% DO SINAL ────────────────────────────────────────────────
@app.route('/agendamentos/gerar-pix-sinal', methods=['POST', 'OPTIONS'])
@app.route('/api/agendamentos/gerar-pix-sinal', methods=['POST', 'OPTIONS'])
def gerar_pix_sinal():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    data = request.json or {}
    valor_total = float(data.get('valor_total', 0.0))
    categoria = data.get('categoria_servico', '')
    cliente_nome = data.get('cliente_nome', 'Cliente')
    servico_nome = data.get('servico_nome', 'Serviço')

    exige_sinal = any(c.lower() in categoria.lower() for c in SERVICOS_COM_SINAL)
    valor_cobranca = (valor_total * 0.5) if exige_sinal else valor_total

    if not sdk:
        return jsonify({
            'exige_sinal': exige_sinal,
            'valor_pago': valor_cobranca,
            'payment_id': 'SIMULADO_12345',
            'qr_code_pix': '00020126580014BR.GOV.BCB.PIX0136123e4567-e89b-12d3-a456-426614174000520400005303986540550.005802BR5913Studio Bella6008SAO PAULO62070503***6304E2CA',
            'qr_code_base64': 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
        }), 201

    try:
        payment_data = {
            "transaction_amount": round(valor_cobranca, 2),
            "description": f"Sinal 50% - {servico_nome} ({cliente_nome})",
            "payment_method_id": "pix",
            "payer": {
                "email": "cliente@email.com",
                "first_name": cliente_nome
            }
        }

        payment_response = sdk.payment().create(payment_data)
        payment = payment_response["response"]

        return jsonify({
            'exige_sinal': exige_sinal,
            'valor_pago': valor_cobranca,
            'payment_id': payment["id"],
            'qr_code_pix': payment["point_of_interaction"]["transaction_data"]["qr_code"],
            'qr_code_base64': payment["point_of_interaction"]["transaction_data"]["qr_code_base64"]
        }), 201

    except Exception as e:
        return jsonify({'error': f'Erro ao gerar Pix no Mercado Pago: {str(e)}'}), 400


# ─── CRIAÇÃO DO AGENDAMENTO UNIFICADO ────────────────────────────────────────
@app.route('/agendamentos', methods=['POST', 'OPTIONS'])
@app.route('/api/agendamentos', methods=['POST', 'OPTIONS'])
def criar_agendamento():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    data = request.json or {}

    try:
        payload = {
            'salao_id': data.get('salao_id'),
            'profissional_id': data.get('profissional_id'),
            'servico_id': data.get('servico_id'),
            'tipo_atendimento': data.get('tipo_atendimento', 'salao'),
            'endereco_rua': data.get('endereco_rua'),
            'endereco_numero': data.get('endereco_numero'),
            'endereco_bairro': data.get('endereco_bairro'),
            'taxa_deslocamento': data.get('taxa_deslocamento', 0.0),
            'mercadopago_id': str(data.get('mercadopago_id', '')),
            'data_hora_inicio': data.get('data_hora_inicio'),
            'status': 'pendente_sinal' if data.get('exige_sinal') else 'agendado',
            'status_pagamento': 'aguardando_pix' if data.get('exige_sinal') else 'pendente'
        }

        if supabase:
            cliente_res = supabase.table('clientes').select('id').eq('salao_id', data['salao_id']) \
                .eq('whatsapp', data['cliente_whatsapp']).execute()

            if cliente_res.data:
                cliente_id = cliente_res.data[0]['id']
            else:
                novo = supabase.table('clientes').insert({
                    'salao_id': data['salao_id'],
                    'nome': data['cliente_nome'],
                    'whatsapp': data['cliente_whatsapp']
                }).execute()
                cliente_id = novo.data[0]['id']

            payload['cliente_id'] = cliente_id
            res = supabase.table('agendamentos').insert(payload).execute()
            return jsonify({'mensagem': 'Agendamento registrado!', 'agendamento': res.data[0]}), 201

        return jsonify({'mensagem': 'Agendamento simulado!', 'agendamento': payload}), 201

    except Exception as e:
        return jsonify({'error': f'Erro ao salvar no banco: {str(e)}'}), 400


# ─── WEBHOOK MERCADO PAGO ─────────────────────────────────────────────────────
@app.route('/webhooks/mercadopago', methods=['POST'])
@app.route('/api/webhooks/mercadopago', methods=['POST'])
def webhook_mercadopago():
    data = request.json or {}
    if data.get("type") == "payment" and sdk and supabase:
        payment_id = data["data"]["id"]
        payment_info = sdk.payment().get(payment_id)["response"]

        if payment_info.get("status") == "approved":
            supabase.table('agendamentos') \
                .update({'status': 'agendado', 'status_pagamento': 'sinal_pago'}) \
                .eq('mercadopago_id', str(payment_id)) \
                .execute()

    return jsonify({'status': 'ok'}), 200


# Execução Local (Roda apenas via 'python app.py')
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)