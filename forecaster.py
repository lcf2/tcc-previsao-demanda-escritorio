import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split

class MaterialForecaster:
    """
    Classe responsável pela inteligência preditiva do sistema de Supply Chain.
    Implementa o algoritmo Random Forest Regressor para previsão de demanda de Materiais.
    """
    def __init__(self, n_estimators=100, max_depth=10):
        self.model = RandomForestRegressor(n_estimators=n_estimators, max_depth=max_depth, random_state=42)
        self.train_columns = None

    def _prepare_features(self, df):
        """
        Realiza a engenharia de atributos (Feature Engineering):
        - Extrai Mês e Ano.
        - Cria Lags de 1 e 2 meses para capturar tendências temporais.
        """
        df = df.copy()
        df['Mes'] = df['Data'].dt.month
        df['Ano'] = df['Data'].dt.year
        
        # Ordenar por data para garantir lags corretos
        df = df.sort_values(['Setor', 'Material', 'Data'])
        
        # Criar Lags por grupo (Setor/Material) para evitar vazamento de dados
        df['Lag_1'] = df.groupby(['Setor', 'Material'])['Quantidade_Consumida'].shift(1)
        df['Lag_2'] = df.groupby(['Setor', 'Material'])['Quantidade_Consumida'].shift(2)
        
        # Preencher NaNs iniciais com a média do grupo para não perder muitos dados
        df['Lag_1'] = df.groupby(['Setor', 'Material'])['Lag_1'].transform(lambda x: x.fillna(x.mean()))
        df['Lag_2'] = df.groupby(['Setor', 'Material'])['Lag_2'].transform(lambda x: x.fillna(x.mean()))
        
        # Último recurso se ainda houver NaNs (ex: séries muito curtas)
        df = df.fillna(0)
        
        return df

    def train(self, df_consumo):
        """
        Treina o modelo e retorna métricas de performance.
        Protocolo: Divisão Temporal (sem shuffle) para respeitar a cronologia.
        """
        df_prepared = self._prepare_features(df_consumo)
        
        # One-Hot Encoding para variáveis categóricas (Setor e Material)
        df_ml = pd.get_dummies(df_prepared, columns=['Setor', 'Material'])
        
        X = df_ml.drop(['Data', 'Quantidade_Consumida'], axis=1)
        y = df_ml['Quantidade_Consumida']
        
        self.train_columns = X.columns
        
        # Divisão 80/20 (Treino/Teste)
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
        
        self.model.fit(X_train, y_train)
        
        y_pred = self.model.predict(X_test)
        mae = mean_absolute_error(y_test, y_pred)
        
        return mae, X_test, y_test, y_pred

    def predict_next_3_months(self, df_consumo):
        """
        Gera previsões recursivas para o próximo trimestre (90 dias).
        """
        if self.train_columns is None:
            raise ValueError("O modelo precisa ser treinado antes de prever.")
            
        last_date = df_consumo['Data'].max()
        future_dates = pd.date_range(last_date + pd.DateOffset(months=1), periods=3, freq='MS')
        
        sectors = df_consumo['Setor'].unique()
        materials = df_consumo['Material'].unique()
        
        future_forecasts = []
        
        # Para cada mês do trimestre futuro
        for date in future_dates:
            for sector in sectors:
                for material in materials:
                    # Pegar os últimos dados conhecidos para os Lags
                    history_slice = df_consumo[(df_consumo['Setor'] == sector) & (df_consumo['Material'] == material)]
                    
                    if not history_slice.empty:
                        lag1 = history_slice['Quantidade_Consumida'].iloc[-1]
                        lag2 = history_slice['Quantidade_Consumida'].iloc[-2] if len(history_slice) > 1 else lag1
                    else:
                        lag1, lag2 = 0, 0
                    
                    future_forecasts.append({
                        'Data': date,
                        'Setor': sector,
                        'Material': material,
                        'Mes': date.month,
                        'Ano': date.year,
                        'Lag_1': lag1,
                        'Lag_2': lag2
                    })
        
        df_future = pd.DataFrame(future_forecasts)
        
        # Aplicar One-Hot Encoding e alinhar colunas
        df_future_ml = pd.get_dummies(df_future, columns=['Setor', 'Material'])
        df_future_ml = df_future_ml.reindex(columns=self.train_columns, fill_value=0)
        
        preds = self.model.predict(df_future_ml)
        df_future['Previsao_Bruta'] = preds.round().astype(int)
        
        return df_future
