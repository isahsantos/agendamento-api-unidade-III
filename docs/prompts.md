# Experimento: dois tipos de prompt para testes de integração

## Prompt 1 — Funcional (caixa-preta)

> Atue como analista de QA. Considere uma API REST Flask de agendamentos com os endpoints POST /api/agendamentos/gerar-pix-sinal, POST /api/agendamentos e POST /api/webhooks/mercadopago. Gere testes de integração usando o cliente HTTP do Flask, considerando: serviços que exigem sinal de 50% (Progressiva, Mechas, Química, Selagem e Balayage); serviços que não exigem sinal; criação de agendamento pendente de sinal; e eventos de webhook irrelevantes. Para cada caso, informe entrada, status HTTP e campos da resposta. Não invente validações que o código não implementa. Use dados sintéticos e não acione serviços externos reais.

**Ajuste do prompt:** exigir status HTTP observável, dados sintéticos e não inventar validações, evitando testes que presumam regras inexistentes.

## Prompt 2 — Estrutural (caixa-branca)

> Atue como engenheira de testes Python. Analise as funções criar_agendamento e webhook_mercadopago no app.py deste repositório. Gere testes com pytest e Flask test_client que verifiquem a comunicação com Supabase e Mercado Pago usando mocks: (1) criar cliente e agendamento, (2) reutilizar cliente existente, (3) atualizar agendamento quando pagamento for approved e (4) não atualizar quando pagamento for pending. Inspecione as chamadas de table(), insert(), update() e eq(). Não faça chamadas reais a APIs nem use credenciais de produção. Diferencie comportamento atual de requisitos desejáveis, como idempotência e verificação de autenticidade do webhook.

**Ajuste do prompt:** fornecer nomes das funções e operações de persistência, além de exigir distinção entre comportamento existente e melhorias sugeridas.

## Observação metodológica

Os testes abaixo foram elaborados com assistência de LLM e revisados no código-fonte.
