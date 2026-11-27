//#include <iostream>
//#include <fstream>
//#include <iomanip>

//int main() 
{
    double x;
    const double constant_factor = 0.37581;
    const double multiplier = 7.4;
    std::ofstream outfile("density_results.txt");

    outfile << std::fixed << std::setprecision(2);

    for (x = 0.1; x <= 1.12; x += 0.01) {
        double density = (1 - constant_factor * x) * multiplier;
        outfile << x << "," << density << std::endl;
    }

    outfile.close();
    return 0;
}

