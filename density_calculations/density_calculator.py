import numpy as np
import matplotlib.pyplot as plt

# Define the density as a function of x (Yttrium molar fraction)
def density(x):
    return (1 - 0.37581 * x) * 7.4

# Create an array of x values from 0.02 to 1.12
x_values = np.arange(0.02, 0.14, 0.001)

# Calculate the density for each x value
density_values = density(x_values)

# Save the results to a text file
with open('density_results.txt', 'w') as file:
    for x, p in zip(x_values, density_values):
        file.write(f'{x}, {p}\n')

# Plot the results
plt.figure()
plt.plot(x_values, density_values, label='Density vs Yttrium molar fraction x')
plt.xlabel('Yttrium molar fraction x')
plt.ylabel('Density [g/cm³]')
plt.title('Density as a function of x')
plt.legend()
plt.grid(True)

# Save the plot as PNG and PDF
plt.savefig('density_plot.png')
#plt.savefig('density_plot.pdf')

