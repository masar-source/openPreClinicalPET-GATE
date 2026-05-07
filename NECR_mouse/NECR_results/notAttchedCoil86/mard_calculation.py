import pandas as pd

file_path = 'NECR_MARD_Py.xlsx'
df = pd.read_excel(file_path)

# Define a function to calculate MARD
def calculate_mard(sim, meas):
    return (abs(sim - meas) / meas).mean() * 100

# Calculate MARD for each pair of columns
mard_results = {}
for col in df.columns:
    if "(sim)" in col:
        corresponding_meas_col = col.replace("(sim)", "(meas)")
        if corresponding_meas_col in df.columns:
            mard = calculate_mard(df[col], df[corresponding_meas_col])
            mard_results[col.replace("(sim)", "").strip()] = mard

# Convert the results to a DataFrame
mard_df = pd.DataFrame(mard_results.items(), columns=["Metric", "MARD (%)"])

mard_df.to_csv('MARD_Results.txt', index=False, sep='\t')
#mard_df.to_excel('MARD_Results.xlsx', index=False)


