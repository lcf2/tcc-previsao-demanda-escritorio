import pandas as pd

def apply_inclusive_rules(df_future, df_employees):
    """
    Camada de Pós-Processamento Inclusivo e Ergonômico.
    Cruza as previsões brutas de ML com o cadastro de RH para identificar necessidades 
    especiais e adequar a ordem de compra à norma NR-17.
    """
    report = []
    
    for index, row in df_future.iterrows():
        sector = row['Setor']
        material = row['Material']
        raw_qty = row['Previsao_Bruta']
        date = row['Data']
        
        # Filtrar funcionários do setor com restrições ou necessidades especiais
        sector_employees = df_employees[df_employees['Setor'] == sector]
        restricted_employees = sector_employees[sector_employees['Restricao_Ergonomica'] != "Nenhuma"]
        
        previsao_adaptada = raw_qty
        obs = "Demanda Padrão atendida."
        itens_adaptados = 0
        
        if material == 'Mouses e Teclados':
            # 1. Caso LER/DORT -> Mouse Vertical
            ler_dort = len(restricted_employees[restricted_employees['Restricao_Ergonomica'].str.contains("LER/DORT")])
            
            # 2. Caso Baixa Visão -> Teclado Ampliado
            baixa_visao = len(restricted_employees[restricted_employees['Restricao_Ergonomica'].str.contains("Baixa Visão")])
            
            # 3. Caso Canhoto -> Mouse/Teclado Adaptado
            canhoto = len(restricted_employees[restricted_employees['Restricao_Ergonomica'].str.contains("Canhoto")])
            
            itens_adaptados = ler_dort + baixa_visao + canhoto
            
            if itens_adaptados > 0:
                previsao_adaptada = max(0, raw_qty - itens_adaptados)
                detalhes = []
                if ler_dort > 0: detalhes.append(f"{ler_dort}x Mouse Vertical (LER/DORT)")
                if baixa_visao > 0: detalhes.append(f"{baixa_visao}x Teclado Ampliado (Baixa Visão)")
                if canhoto > 0: detalhes.append(f"{canhoto}x Kit para Canhoto")
                
                obs = f"Adequação NR-17: {', '.join(detalhes)}. Redução no lote comum para evitar ociosidade."
        
        elif material == 'Canetas e Escrita':
            # Exemplo de regra para suporte de punho se houver restrição de postura
            postura = len(restricted_employees[restricted_employees['Restricao_Ergonomica'].str.contains("NR-17")])
            if postura > 0:
                obs = f"Inclusão: Necessário {postura}x Suporte Ortopédico de Punho para este setor (Ergonomia)."

        report.append({
            'Data': date,
            'Setor': sector,
            'Material': material,
            'Previsao_Bruta': raw_qty,
            'Previsao_Comum_Ajustada': int(previsao_adaptada),
            'Itens_Adaptados_Extra': itens_adaptados,
            'Observacao': obs
        })
        
    return pd.DataFrame(report)
