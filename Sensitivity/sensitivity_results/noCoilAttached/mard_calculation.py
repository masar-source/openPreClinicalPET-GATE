import pandas as pd

file_path = 'SensitivityPlot.xlsx'   # 1-sheet file with:
                                     # "Axial Position (mm)", "Measurements", "Simulations"
df = pd.read_excel(file_path)

# ─────────────────────────────
# 1) MARD (same method as yours)
# ─────────────────────────────
def calculate_mard(sim, meas):
    return (abs(sim - meas) / meas).mean() * 100

sim_col = "Simulations"
meas_col = "Measurements"
pos_col = "Axial Position (mm)"

mard = calculate_mard(df[sim_col], df[meas_col])

mard_df = pd.DataFrame(
    [("Sensitivity / Axial profile", mard)],
    columns=["Metric", "MARD (%)"]
)
mard_df.to_csv('MARD_Results.txt', index=False, sep='\t')

# ─────────────────────────────
# 2) ARD per position
#    ARD_i = |sim_i - meas_i| / meas_i * 100
#    Save axial position and corresponding ARD
# ─────────────────────────────
ard_series = (df[sim_col] - df[meas_col]).abs() / df[meas_col] * 100

ard_df = pd.DataFrame({
    pos_col: df[pos_col],
    "ARD (%)": ard_series
})

# if there are rows with 0 or NaN in "Measurements", ARD will be inf or NaN;
# you may drop them if you want strict output:
# ard_df = ard_df.replace([float('inf')], pd.NA).dropna(subset=["ARD (%)"])

ard_df.to_csv('ARD_by_Axial_Position.txt', index=False, sep='\t')

