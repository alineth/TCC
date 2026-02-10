# Agente de reposição para validação

Este repositório contém um agente programado em Python para apoiar decisões de reposição no varejo com previsão de demanda e incerteza de oferta.

## Arquivos

- `retail_agent.py`: implementação do agente e modo de validação por simulação.
- `sample_demand.csv`: série de demanda de exemplo para testes rápidos.
- `introducao.md` e `agente.md`: texto conceitual do TCC.

## Como executar

### 1) Recomendação pontual

```bash
python retail_agent.py --data sample_demand.csv --inventory 140 --on-order 30
```

Saída principal:
- demanda prevista diária;
- estoque de segurança;
- ponto de pedido;
- estoque-alvo;
- pedido recomendado.

### 2) Validação por simulação (backtest simplificado)

```bash
python retail_agent.py --data sample_demand.csv --inventory 140 --on-order 30 --validate
```

Métricas de validação:
- taxa de ruptura;
- estoque médio final;
- falta acumulada;
- quantidade de pedidos emitidos.

## Formato do CSV

O CSV de entrada deve conter ao menos a coluna `demand`.

Exemplo mínimo:

```csv
day,demand
1,21.4
2,25.0
3,22.8
```

## Parâmetros úteis

- `--service-level`: nível de serviço (`0.80`, `0.85`, `0.90`, `0.95`, `0.97`, `0.99`).
- `--review-period`: período de revisão (dias).
- `--lead-time`: lead time médio (dias).
- `--inventory`: estoque disponível atual.
- `--on-order`: estoque em trânsito.
