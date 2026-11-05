import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error


class MaterialForecaster:
    """Random Forest de demanda com validação cronológica por horizonte."""

    def __init__(self, n_estimators=100, max_depth=10):
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.model = None
        self.train_columns = None

    @staticmethod
    def _normalize_history(df_consumo):
        required = {"Data", "Setor", "Material", "Quantidade_Consumida"}
        missing = required.difference(df_consumo.columns)
        if missing:
            raise ValueError(f"Colunas obrigatórias ausentes: {', '.join(sorted(missing))}.")

        history = df_consumo.copy()
        history["Data"] = pd.to_datetime(history["Data"], errors="coerce")
        history["Quantidade_Consumida"] = pd.to_numeric(
            history["Quantidade_Consumida"], errors="coerce"
        )
        if history["Data"].isna().any() or history["Quantidade_Consumida"].isna().any():
            raise ValueError("O histórico contém data ou quantidade inválida.")
        if not np.isfinite(history["Quantidade_Consumida"]).all():
            raise ValueError("O histórico contém quantidade não finita.")
        if (history["Quantidade_Consumida"] < 0).any():
            raise ValueError("O histórico contém quantidades negativas.")
        if history[["Setor", "Material"]].isna().any().any():
            raise ValueError("O histórico contém setor ou material vazio.")

        history["Data"] = history["Data"].dt.to_period("M").dt.to_timestamp()
        keys = ["Data", "Setor", "Material"]
        if history.duplicated(keys).any():
            raise ValueError("O histórico contém mais de um registro por material/setor/mês.")
        return history.sort_values(["Setor", "Material", "Data"]).reset_index(drop=True)

    @staticmethod
    def _prepare_features(history):
        prepared = history.copy()
        prepared["Mes"] = prepared["Data"].dt.month
        prepared["Ano"] = prepared["Data"].dt.year
        groups = ["Setor", "Material"]
        for lag, column in ((1, "Lag_1"), (2, "Lag_2")):
            prepared[column] = prepared.groupby(groups)["Quantidade_Consumida"].shift(lag)
            prepared[column] = prepared.groupby(groups)[column].transform(
                lambda values: values.fillna(values.mean()).fillna(0)
            )
        return prepared

    @staticmethod
    def _encode_features(prepared):
        drop_columns = [
            column for column in (
                "Data", "Quantidade_Consumida", "Categoria", "Subcategoria"
            ) if column in prepared.columns
        ]
        return pd.get_dummies(
            prepared.drop(columns=drop_columns),
            columns=["Setor", "Material"],
        )

    def _new_model(self):
        return RandomForestRegressor(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            random_state=42,
            n_jobs=1,
        )

    @staticmethod
    def _series_values(history):
        return {
            key: group.sort_values("Data")["Quantidade_Consumida"].astype(float).tolist()
            for key, group in history.groupby(["Setor", "Material"], sort=True)
        }

    def _predict_dates(self, history, forecast_dates):
        if self.model is None or self.train_columns is None:
            raise ValueError("O modelo precisa ser treinado antes de prever.")

        rolling_values = self._series_values(history)
        generated = []
        for date in forecast_dates:
            rows = []
            for (sector, material), values in rolling_values.items():
                lag_1 = values[-1]
                lag_2 = values[-2] if len(values) > 1 else lag_1
                rows.append({
                    "Data": date,
                    "Setor": sector,
                    "Material": material,
                    "Mes": date.month,
                    "Ano": date.year,
                    "Lag_1": lag_1,
                    "Lag_2": lag_2,
                })

            future_features = pd.get_dummies(
                pd.DataFrame(rows),
                columns=["Setor", "Material"],
            ).reindex(columns=self.train_columns, fill_value=0)
            predictions = np.rint(np.maximum(self.model.predict(future_features), 0))
            for row, prediction in zip(rows, predictions):
                quantity = float(prediction)
                rolling_values[(row["Setor"], row["Material"])].append(quantity)
                generated.append({
                    "Data": date,
                    "Setor": row["Setor"],
                    "Material": row["Material"],
                    "Previsao": quantity,
                })
        return pd.DataFrame(generated)

    def _fit(self, history):
        prepared = self._prepare_features(history)
        features = self._encode_features(prepared)
        self.train_columns = features.columns
        self.model = self._new_model()
        self.model.fit(features, history["Quantidade_Consumida"].astype(float))

    def train(self, df_consumo):
        """Avalia um holdout temporal recursivo e depois ajusta o modelo no histórico inteiro."""
        history = self._normalize_history(df_consumo)
        dates = pd.DatetimeIndex(history["Data"].drop_duplicates().sort_values())
        split_index = int(len(dates) * 0.8)
        if split_index < 3 or split_index >= len(dates):
            raise ValueError("São necessários pelo menos quatro meses para validação temporal.")

        training_dates = dates[:split_index]
        test_dates = dates[split_index:]
        cutoff = training_dates[-1]
        training = history[history["Data"] <= cutoff].copy()
        actual = history[history["Data"].isin(test_dates)].copy()

        training_groups = set(training[["Setor", "Material"]].itertuples(index=False, name=None))
        actual_groups = set(actual[["Setor", "Material"]].itertuples(index=False, name=None))
        if training_groups != actual_groups:
            raise ValueError(
                "O período de teste contém materiais/setores sem histórico de treinamento."
            )
        expected_points = len(training_groups) * len(test_dates)
        if len(actual) != expected_points:
            raise ValueError("O período de teste não tem todos os meses para cada série.")

        self._fit(training)
        predictions = self._predict_dates(training, test_dates)
        comparison = actual[["Data", "Setor", "Material", "Quantidade_Consumida"]].merge(
            predictions,
            on=["Data", "Setor", "Material"],
            validate="one_to_one",
        )
        mae = mean_absolute_error(
            comparison["Quantidade_Consumida"],
            comparison["Previsao"],
        )

        # Refit on all observations only after the holdout score is finalized.
        self._fit(history)
        return (
            float(mae),
            comparison[["Data", "Setor", "Material"]],
            comparison["Quantidade_Consumida"].reset_index(drop=True),
            comparison["Previsao"].to_numpy(),
        )

    def predict_next_3_months(self, df_consumo):
        """Forecast each existing sector/material series recursively for three months."""
        history = self._normalize_history(df_consumo)
        if self.model is None or self.train_columns is None:
            raise ValueError("O modelo precisa ser treinado antes de prever.")

        last_date = history["Data"].max()
        future_dates = pd.date_range(
            last_date + pd.offsets.MonthBegin(1),
            periods=3,
            freq="MS",
        )
        forecasts = self._predict_dates(history, future_dates)
        forecasts["Previsao_Bruta"] = forecasts["Previsao"].astype(int)
        return forecasts.drop(columns="Previsao")
