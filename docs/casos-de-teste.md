# Casos de teste de integração

| ID | Abordagem | Cenário | Resultado esperado |
|---|---|---|---|
| F01 | Funcional | Pix para Progressiva (R$ 240) | HTTP 201, sinal R$ 120 |
| F02 | Funcional | Pix para Mechas (R$ 300) | HTTP 201, sinal R$ 150 |
| F03 | Funcional | Pix para Corte (R$ 80) | HTTP 201, cobrança R$ 80 |
| F04 | Funcional | Agendamento com sinal, sem banco configurado | HTTP 201, status pendente_sinal/aguardando_pix, resposta simulada |
| F05 | Funcional | Webhook de tipo irrelevante | HTTP 200, status ok |
| E01 | Estrutural | Novo cliente + novo agendamento | Dois inserts e cliente_id associado |
| E02 | Estrutural | Cliente já cadastrado | Reutilização do ID sem novo insert de cliente |
| E03 | Estrutural | Pagamento aprovado | Update de status para agendado/sinal_pago |
| E04 | Estrutural | Pagamento pendente | Sem update no Supabase |

**Limitação:** mocks verificam integração entre componentes de aplicação, não uma transação real no banco nem o processamento real pelo Mercado Pago.

## Riscos identificados no código (não afirmar que estão corrigidos)

- Webhook não apresenta validação explícita de assinatura/autenticidade.
- `POST /agendamentos` possui caminho de resposta simulada quando o Supabase está ausente.
- Não há validação explícita de disponibilidade/conflito de horários na criação do agendamento.
- A criação de cliente e agendamento ocorre em operações distintas, sem transação explícita no código mostrado.
- Endpoint de Pix retorna resposta simulada quando o SDK não está configurado.
