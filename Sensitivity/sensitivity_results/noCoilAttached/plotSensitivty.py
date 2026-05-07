import pandas as pd
import matplotlib.pyplot as plt

file_path = 'SensitivityPlot_noCoilAttached.xlsx'
data = pd.read_excel(file_path)

axial_position = data['Axial Position (mm)']
measurements = data['Measurements']
simulations = data['Simulations']

plt.figure(figsize=(8, 6))

plt.plot(axial_position, measurements, label='Measurements', marker='o', markersize=3, color='black', linestyle='-', linewidth=1.4)

plt.plot(axial_position, simulations, label='Simulations', marker='x', markersize=3, color='red', linestyle='-', linewidth=1.4)

#plt.title('Sensitivity', fontsize=20, fontweight='normal')
plt.xlabel('Axial Position (mm)', fontsize=18, fontweight='normal')
plt.ylabel('Absolute Sensitivity %', fontsize=18, fontweight='normal')
plt.legend(fontsize=14, loc='best', frameon=True)

plt.grid(True)

plt.ylim(0, 10)
plt.yticks(range(0, 11, 1), fontsize=14)

plt.xlim(-80, 80)
plt.xticks(fontsize=14)


plt.axvline(0, color='black', linewidth=1, linestyle=(0, (1, 5)))


plt.savefig('sensitivity_profile.png')

plt.show()

