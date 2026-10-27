"""Data preprocessing and leakage-safe imputation utilities."""

import pandas as pd


class LeakageSafePreprocessor:
    """Preprocesses raw hospital telemetry with strict temporal leakage prevention.

    Imputation rules:
    - Forward-fill (`ffill()`) only propagates past historical observations forward in time.
    - Backward-fill (`bfill()`) or full-dataset global means are strictly prohibited because
      they leak future time-series information into historical records.
    - Missingness indicators are preserved as explicit informative features.
    """

    @staticmethod
    def clean_and_impute(
        df: pd.DataFrame,
        value_cols: list[str] | None = None,
        group_cols: list[str] | None = None,
    ) -> pd.DataFrame:
        """Impute missing telemetry observations strictly using past observations.

        Parameters
        ----------
        df : pd.DataFrame
            Raw panel dataset containing temporal observations.
        value_cols : list[str], optional
            Columns to impute, by default ['observed_consumption_units', 'reported_inventory_units'].
        group_cols : list[str], optional
            Grouping series, by default ['hospital_id', 'category_id'].

        Returns
        -------
        pd.DataFrame
            Cleaned dataframe with imputed values and missingness flags preserved.
        """
        if value_cols is None:
            value_cols = ["observed_consumption_units", "reported_inventory_units"]
        if group_cols is None:
            group_cols = ["hospital_id", "category_id"]

        df_clean = df.copy()
        # Ensure chronological ordering prior to sequential imputation
        df_clean = df_clean.sort_values(by=["date"] + group_cols).reset_index(drop=True)

        for col in value_cols:
            if col in df_clean.columns:
                # Mask out entries flagged as missing report
                if "missing_report_flag" in df_clean.columns:
                    mask_missing = df_clean["missing_report_flag"] == 1
                    df_clean.loc[mask_missing, col] = None

                # Forward-fill past known state per facility and category
                df_clean[col] = df_clean.groupby(group_cols)[col].ffill()

                # For the very beginning of the series if initial days are missing,
                # fill with the first available non-null observation (initialization prior)
                # or 0.0 to prevent NaNs
                df_clean[col] = df_clean[col].fillna(0.0)

        return df_clean
