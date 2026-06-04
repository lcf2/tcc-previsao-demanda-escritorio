import pandas as pd

def apply_inclusive_rules(df_future, df_employees):
    """
    Camada de Pós-Processamento Inclusivo.
    Cruza as previsões brutas de ML com o cadastro de RH para identificar restrições ergonômicas
    e ajustar o volume de compras, evitando desperdício de peças não utilizadas.
    """
    report = []
    
    for index, row in df_future.iterrows():
        sector = row['Setor']
        epi = row['EPI']
        raw_qty = row['Previsao_Bruta']
        date = row['Data']
        
        # Filtrar funcionários do setor com restrições
        sector_employees = df_employees[df_employees['Setor'] == sector]
        pcd_employees = sector_employees[sector_employees['Restricao_Ergonomica'] != "Nenhuma"]
        
        previsao_adaptada = raw_qty
        obs = "Demanda Padrão"
        descarte_evitado = 0
        
        if epi == 'Luva Nitrílica':
            # Identificar amputações que fracionam o par de luvas
            esq_only = len(pcd_employees[pcd_employees['Restricao_Ergonomica'].str.contains("Mão Direita")])
            dir_only = len(pcd_employees[pcd_employees['Restricao_Ergonomica'].str.contains("Mão Esquerda")])
            
            if esq_only > 0 or dir_only > 0:
                # Se temos pessoas que usam apenas um lado, podemos comprar luvas avulsas
                # ou subtrair o lado não utilizado do estoque/compra de pares.
                # Aqui simulamos a economia de não comprar o par completo para quem não usa.
                descarte_evitado = esq_only + dir_only
                previsao_adaptada = max(0, raw_qty - (descarte_evitado / 2)) # Ajuste simplificado
                obs = f"Economia Circular: {descarte_evitado} luvas avulsas otimizadas (PCD)."
                
        elif epi == 'Bota de Segurança':
            ortopedico = len(pcd_employees[pcd_employees['Restricao_Ergonomica'].str.contains("Ortopédico")])
            if ortopedico > 0:
                obs = f"Atenção: {ortopedico} bota(s) sob medida necessária(s) para este setor."
        
        report.append({
            'Data': date,
            'Setor': sector,
            'EPI': epi,
            'Previsao_Bruta': raw_qty,
            'Previsao_Adaptada': round(previsao_adaptada, 1),
            'Descarte_Evitado_Un': descarte_evitado,
            'Observacao': obs
        })
        
    return pd.DataFrame(report)
