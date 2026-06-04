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
    # Colunas: Data, EPI, Setor, Quantidade_Consumida
    start_date = datetime(2024, 1, 1)
    dates = pd.date_range(start_date, periods=24, freq='MS')
    
    sectors = ['Produção', 'Logística', 'Manutenção', 'Qualidade']
    epis = ['Luva Nitrílica', 'Bota de Segurança', 'Óculos de Proteção', 'Protetor Auricular']
    
    consumption_data = []
    for date in dates:
        # Simular sazonalidade simples
        seasonality = 1 + 0.2 * np.sin(2 * np.pi * date.month / 12)
        for sector in sectors:
            for epi in epis:
                base_lambda = {
                    'Luva Nitrílica': 50,
                    'Bota de Segurança': 10,
                    'Óculos de Proteção': 15,
                    'Protetor Auricular': 20
                }[epi]
                
                sector_factor = {'Produção': 1.5, 'Logística': 1.2, 'Manutenção': 1.0, 'Qualidade': 0.8}[sector]
                
                # Distribuição de Poisson para simular variabilidade real
                lambda_val = base_lambda * sector_factor * seasonality
                quantity = np.random.poisson(lambda_val)
                
                consumption_data.append({
                    'Data': date,
                    'EPI': epi,
                    'Setor': sector,
                    'Quantidade_Consumida': quantity
                })
    
    df_consumo = pd.DataFrame(consumption_data)
    
    # 2. Gerar Cadastro de Colaboradores (Equipe Ativa)
    # Colunas: Colaborador_ID, Nome, Setor, Tamanho_Luva, Tamanho_Bota, Restricao_Ergonomica
    n_colabs = 150
    colabs_data = []
    
    # Definir 8% de PCD/Restrições conforme solicitado
    restrictions_pool = [
        "Amputação Mão Esquerda (Usa apenas luva Direita)",
        "Amputação Mão Direita (Usa apenas luva Esquerda)",
        "Calçado Ortopédico Customizado"
    ]
    
    for i in range(1, n_colabs + 1):
        is_pcd = np.random.random() < 0.08
        restricao = np.random.choice(restrictions_pool) if is_pcd else "Nenhuma"
        
        colabs_data.append({
            'Colaborador_ID': f'COLAB-{i:03d}',
            'Nome': f'Colaborador Nome {i}',
            'Setor': np.random.choice(sectors),
            'Tamanho_Luva': np.random.choice(['P', 'M', 'G', 'GG']),
            'Tamanho_Bota': np.random.choice(list(range(35, 46))),
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
