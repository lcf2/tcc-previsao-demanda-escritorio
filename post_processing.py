import pandas as pd 
 
def apply_inclusive_rules(df_future, df_employees): 
    """ 
    Cruza as previsões brutas de materiais de escritório com as necessidades ergonômicas 
    do cadastro de colaboradores (RH) por setor para gerar um plano de compras adaptado. 
    
    Implementa a conformidade com a NR-17 e diretrizes de acessibilidade (ESG). 
    """ 
    # Cria uma cópia do dataframe de previsões futuras para não modificar o original 
    df_output = df_future.copy() 
    
    # Normaliza a identificação das colunas de identificação e quantidade 
    material_col = 'EPI' if 'EPI' in df_output.columns else 'Material' 
    prev_col = 'Previsao_Bruta' if 'Previsao_Bruta' in df_output.columns else ('Quantidade_Prevista' if 'Quantidade_Prevista' in df_output.columns else 'Previsao') 
    
    # Inicializa as novas colunas adaptativas padrão 
    df_output['Previsao_Adaptada'] = df_output[prev_col] 
    df_output['Quantidade_Especial'] = 0 
    df_output['Item_Especial'] = "Nenhum" 
    df_output['Observacao'] = "Nenhuma adequação ergonômica pendente para este material no setor." 
    
    # Processa cada previsão futura linha a linha 
    for idx, row in df_output.iterrows(): 
        setor = row['Setor'] 
        material = row[material_col] 
        qtd_bruta = row[prev_col] 
        
        # Filtra os colaboradores que atuam no respectivo setor 
        colabs_setor = df_employees[df_employees['Setor'] == setor] 
        
        # ============================================================================== 
        # CRÍTICO: Inicialização segura da lista de detalhes por linha para evitar NameError! 
        # ============================================================================== 
        detalhes = [] 
        pcds_ativos = 0 
        item_adaptado = "Nenhum" 
        
        # --- REGRA 1: Mouses e Teclados + LER/DORT (NR-17) --- 
        if "mouse" in material.lower() or "teclado" in material.lower(): 
            pcds = colabs_setor[colabs_setor['Restricao_Ergonomica'].str.contains("LER/DORT", na=False, case=False)] 
            pcds_ativos = len(pcds) 
            if pcds_ativos > 0: 
                item_adaptado = "Combo Mouse Vertical + Teclado Split Ergonômico" 
                # Subtrai o equivalente de itens comuns e converte em especiais 
                qtd_comum_ajustada = max(0, qtd_bruta - pcds_ativos) 
                df_output.at[idx, 'Previsao_Adaptada'] = qtd_comum_ajustada 
                df_output.at[idx, 'Quantidade_Especial'] = pcds_ativos 
                df_output.at[idx, 'Item_Especial'] = item_adaptado 
                detalhes.append(f"{pcds_ativos}x {item_adaptado}") 
        
        # --- REGRA 2: Rotulador Brother + Baixa Visão (Inclusão Visual) --- 
        elif "rotulador" in material.lower(): 
            pcds = colabs_setor[colabs_setor['Restricao_Ergonomica'].str.contains("Visual|Visão", na=False, case=False)] 
            pcds_ativos = len(pcds) 
            if pcds_ativos > 0: 
                item_adaptado = "Rotulador com Teclas de Auto-Relevo/Braille" 
                qtd_comum_ajustada = max(0, qtd_bruta - pcds_ativos) 
                df_output.at[idx, 'Previsao_Adaptada'] = qtd_comum_ajustada 
                df_output.at[idx, 'Quantidade_Especial'] = pcds_ativos 
                df_output.at[idx, 'Item_Especial'] = item_adaptado 
                detalhes.append(f"{pcds_ativos}x {item_adaptado}") 
                
        # --- REGRA 3: Cadeiras Giratórias + Suporte Postura (NR-17) --- 
        elif "cadeira" in material.lower(): 
            pcds = colabs_setor[colabs_setor['Restricao_Ergonomica'].str.contains("Postura|NR-17", na=False, case=False)] 
            pcds_ativos = len(pcds) 
            if pcds_ativos > 0: 
                item_adaptado = "Cadeiras Ergonômicas Ajustáveis Premium (NR-17)" 
                qtd_comum_ajustada = max(0, qtd_bruta - pcds_ativos) 
                df_output.at[idx, 'Previsao_Adaptada'] = qtd_comum_ajustada 
                df_output.at[idx, 'Quantidade_Especial'] = pcds_ativos 
                df_output.at[idx, 'Item_Especial'] = item_adaptado 
                detalhes.append(f"{pcds_ativos}x {item_adaptado}") 
                
        # --- REGRA 4: Canetas e Escrita + Colaborador Canhoto (Biotipos) --- 
        elif "caneta" in material.lower() or "escrita" in material.lower(): 
            pcds = colabs_setor[colabs_setor['Restricao_Ergonomica'].str.contains("Canhoto", na=False, case=False)] 
            pcds_ativos = len(pcds) 
            if pcds_ativos > 0: 
                item_adaptado = "Canetas Ergonômicas Canhotas" 
                qtd_comum_ajustada = max(0, qtd_bruta - pcds_ativos) 
                df_output.at[idx, 'Previsao_Adaptada'] = qtd_comum_ajustada 
                df_output.at[idx, 'Quantidade_Especial'] = pcds_ativos 
                df_output.at[idx, 'Item_Especial'] = item_adaptado 
                detalhes.append(f"{pcds_ativos}x {item_adaptado}") 
        
        # Se alguma adaptação foi registrada para esta linha, consolida na observação 
        if detalhes: 
            df_output.at[idx, 'Observacao'] = ( 
                f"Ajuste NR-17/Inclusão: Encomendar " + " e ".join(detalhes) + 
                " sob medida e reduzir lote comum." 
            ) 
            
    return df_output 
