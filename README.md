# Unidade III — GenAI aplicada a testes de integração

Projeto de referência: **AgendaFácil**, backend Flask com Supabase e Mercado Pago.

## Cenário

Integração de agendamentos com geração de Pix, persistência de clientes/agendamentos e confirmação de pagamento por webhook.

## Como executar

1. Criar ambiente virtual: `python -m venv .venv`
2. Ativar o ambiente (Linux/macOS): `source .venv/bin/activate`
3. Instalar: `pip install -r requirements-test.txt`
4. Executar: `python -m pytest -q`

Os testes utilizam `Flask.test_client` e mocks, sem pagamentos reais e sem gravar em banco de produção. Não use credenciais reais de produção para testar.

## Documentação

- `docs/prompts.md`: dois prompts e refinamentos
- `docs/casos-de-teste.md`: matriz de casos e riscos
- `docs/resultados.md`: registrar execução real
- `tests/`: implementação dos testes

## Análise comparativa

O prompt funcional prioriza códigos HTTP, payloads e regras observáveis. O estrutural explora chamadas ao banco, reutilização de clientes e transições de pagamento. A combinação amplia a diversidade dos casos; a revisão humana é essencial para distinguir comportamento implementado de requisitos que ainda não existem.

## Segurança

O arquivo `.env` original foi **excluído** desta cópia por poder conter credenciais. Antes de publicar o repositório original, verifique o histórico Git e revogue/rotacione quaisquer credenciais que tenham sido expostas. Adicionar `.env` ao `.gitignore` não apaga versões já commitadas.
