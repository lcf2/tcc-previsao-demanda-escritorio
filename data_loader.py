import pandas as pd
import numpy as np
from datetime import datetime

def generate_synthetic_data():
    """
    Gera dados sintéticos para simular o consumo de EPIs e o cadastro de colaboradores.
    Retorna dois DataFrames: df_consumo e df_colaboradores.
    """
    np.random.seed(42)
    
    # 1. Gerar Histórico de Consumo (mínimo 24 meses)
    # Colunas: Data, Material, Setor, Quantidade_Consumida
    start_date = datetime(2024, 1, 1)
    dates = pd.date_range(start_date, periods=24, freq='MS')
    
    sectors = ['Administrativo', 'Financeiro', 'RH', 'TI', 'Operações']
    materials = ['Papel A4 (Pacotes)', 'Toner de Impressora', 'Canetas e Escrita', 'Mouses e Teclados']
    
    consumption_data = []
    for date in dates:
        # Simular sazonalidade simples (maior consumo no início do ano/semestre)
        seasonality = 1 + 0.15 * np.sin(2 * np.pi * date.month / 12)
        for sector in sectors:
            for material in materials:
                base_lambda = {
                    'Papel A4 (Pacotes)': 80,
                    'Toner de Impressora': 8,
                    'Canetas e Escrita': 30,
                    'Mouses e Teclados': 12
                }[material]
                
                sector_factor = {
                    'Administrativo': 1.4, 
                    'Financeiro': 1.2, 
                    'RH': 1.1, 
                    'TI': 0.9, 
                    'Operações': 0.7
                }[sector]
                
                # Distribuição de Poisson para simular variabilidade real
                lambda_val = base_lambda * sector_factor * seasonality
                quantity = np.random.poisson(lambda_val)
                
                consumption_data.append({
                    'Data': date,
                    'Material': material,
                    'Setor': sector,
                    'Quantidade_Consumida': quantity
                })
    
    df_consumo = pd.DataFrame(consumption_data)
    
    # 2. Gerar Cadastro de Colaboradores (Equipe Ativa)
    # Colunas: Colaborador_ID, Nome, Setor, Restricao_Ergonomica
    n_colabs = 200
    colabs_data = []
    
    # Restrições ergonômicas alinhadas ao novo escopo
    restrictions_pool = [
        "Diagnóstico de LER/DORT (Necessita de Mouse Vertical Ergonômico)",
        "Deficiência Visual/Baixa Visão (Necessita de Teclado Ampliado com Alto Contraste)",
        "Canhoto (Necessita de Teclado/Mouse adaptado)",
        "Restrição de Postura NR-17 (Necessita de Suporte Ortopédico de Punho)"
    ]
    
    for i in range(1, n_colabs + 1):
        is_pcd_or_restricted = np.random.random() < 0.12 # 12% de taxa de inclusão/necessidade
        restricao = np.random.choice(restrictions_pool) if is_pcd_or_restricted else "Nenhuma"
        
        colabs_data.append({
            'Colaborador_ID': f'COLAB-{i:03d}',
            'Nome': f'Colaborador Nome {i}',
            'Setor': np.random.choice(sectors),
            'Restricao_Ergonomica': restricao
        })
        
    df_colaboradores = pd.DataFrame(colabs_data)
    
    return df_consumo, df_colaboradores

def load_from_excel(file_path_consumption, file_path_employees):
    """
    Carregamento de planilhas reais via Pandas.
    """
    try:
        df_consumo = pd.read_excel(file_path_consumption)
        df_colaboradores = pd.read_excel(file_path_employees)
        return df_consumo, df_colaboradores
    except Exception as e:
        print(f"Erro ao carregar arquivos: {e}")
        return None, None
