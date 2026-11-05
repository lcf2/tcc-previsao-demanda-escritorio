# Comparação temporal: Random Forest × FastTree

## Modelos

- **Python:** `RandomForestRegressor` do scikit-learn, implementado em `forecaster.py` e avaliado no benchmark por `benchmark.py`.
- **C#:** FastTree Regression do ML.NET, um método de gradient boosting, avaliado pelo endpoint `POST /api/benchmark`.

O projeto Python não depende de uma biblioteca chamada `supplychain`: “supply chain” descreve o domínio da aplicação. Os modelos de previsão encontrados são Random Forest e FastTree.

## Protocolo do benchmark integrado

1. A base mensal ativa é preparada no dashboard Python.
2. O corte temporal é inclusivo: os dois modelos treinam até o mesmo mês e preveem os três meses seguintes recursivamente.
3. O Python envia o histórico ao serviço C#. Assim, ambos recebem as mesmas observações e as mesmas datas de corte e teste.
4. Antes de mostrar o resultado, o dashboard confere a quantidade de pontos, o total real e os valores reais por série/mês.
5. Os modelos são comparados com uma referência simples que mantém, em cada série, o último consumo observado no horizonte.

As métricas do benchmark são:

- **MAE** e **RMSE**: erro em unidades; menor é melhor.
- **WAPE**: erro absoluto total dividido pelo volume real; menor é melhor. Se o volume real for zero, a métrica não é definida.
- **Viés e totais**: ajudam a identificar previsões sistematicamente acima ou abaixo do consumo.
- **Treino, previsão, CPU e memória**: medidas de uma execução. A memória é amostrada no processo completo do dashboard, não isolada no algoritmo.

Os dois métodos usam a mesma quantidade de árvores configurada na interface, mas têm parâmetros próprios: profundidade para Random Forest e folhas, mínimo de exemplos por folha e taxa de aprendizado para FastTree. Para uma comparação conclusiva, os hiperparâmetros devem ser ajustados separadamente com o mesmo protocolo temporal, sem consultar os períodos de teste.

## Interpretação

O benchmark atual avalia um corte de cada vez. Um modelo com menor erro nesse recorte **não está comprovado como melhor em todos os períodos**. Para uma conclusão acadêmica, repita a avaliação em vários cortes cronológicos, mantenha os períodos futuros fora do treinamento e compare resultados agregados (por exemplo, mediana do MAE/WAPE). Compare também cada modelo com o baseline simples.

Os gráficos e totais do benchmark são agregados. A interface de captura não mostra nomes, códigos ou textos dos materiais, nem oferece exportação dos dados.

## Limitações do problema modelado

- A aplicação prevê **consumo mensal**; ainda não calcula ponto de reposição, estoque de segurança ou lote de compra.
- A base de movimentações não fornece setor ou cadastro de RH; quando importada, as séries são agrupadas no setor genérico configurado pelo importador.
- O importador ainda não classifica tipos de movimento SAP: soma todas as quantidades assinadas por material/mês e converte o saldo negativo em consumo positivo. Confirme o mapeamento de saídas, entradas e estornos com a área responsável antes de usar as previsões para decisões de compra.
- Meses ausentes são tratados como consumo zero pelo importador; essa regra só é válida se o extrato estiver completo para todos os períodos.
- As features atuais são mês, ano, categoria de série e lags curtos. Sazonalidade anual, calendário de dias úteis, promoções, preços, rupturas de estoque e lead time do fornecedor não estão modelados.
- As medições de velocidade e memória são indicativas, dependem do runtime e do processo completo, e devem ser repetidas em condições iguais. Como ambos rodam localmente, não existe custo de API/cloud medido pelo benchmark.

## Validação executada

- Teste sintético verificou o holdout temporal recursivo do Random Forest, a geração de três meses por série e o cálculo das métricas.
- Teste de integração sintético confirmou que Python e C# recebem o mesmo número de pontos, o mesmo total real e o mesmo resultado para o baseline.
- `dotnet build` concluído com zero erros. O ambiente reportou um aviso preexistente de resolução de versão do Swashbuckle e o uso de SDK .NET preview.

Os testes sintéticos confirmam o funcionamento do fluxo; não substituem a validação do sinal das movimentações nem uma avaliação em múltiplos cortes com a base operacional.
