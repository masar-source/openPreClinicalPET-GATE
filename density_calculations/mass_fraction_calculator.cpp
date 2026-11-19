//////////////////////////////////////////////////////
//						    //
// Run: root mass_fraction_calculator.C	            //
//						    //
//////////////////////////////////////////////////////

{ 
   gROOT->Reset();

   // LYSO chemical formula: Lu_2(1-x)*Y_2x*Si*O_5 or 2(1-x)Lu*2xY*Si*5O
   
   float x = 0.108; // The molar fraction of Yttirium
      
   float M_Lu   = 174.97;  //Molecular mass of Lutetium
   float M_Y    = 88.906;  //Molecular mass of Yttrium
   float M_Si   = 28.086;  //Molecular mass of Silicon
   float M_O    = 15.999;  //Molecular mass of Oxygen
   
   float M_LYSO = 2*(1-x)*M_Lu + 2*x*M_Y + M_Si + 5*M_O;  //Total mass of LYSO
   
   float f_Lu   = 2*(1-x)*M_Lu/M_LYSO;  //Mass fraction of Lutetium
   float f_Y    = 2*x*M_Y/M_LYSO;       //Mass fraction of Yttrium
   float f_Si   = M_Si/M_LYSO;		//Mass fraction of Silicon
   float f_O    = 5*M_O/M_LYSO;		//Mass fraction of Oxygen
   
   double d = (1 - 0.37581 * x) * 7.4;

   cout << endl;     
   cout << " ******************************************************************************** " << endl;
   cout << " *                                     INPUTS                    	            * " << endl;
   cout << " ******************************************************************************** " << endl;   
   cout << endl;     
   cout << " Molar fraction of Yttirium: x = " << x << endl << endl;
   cout << " Molecular mass of Lutetium: "       << M_Lu <<  " amu" << endl;
   cout << " Molecular mass of Yttrium:  " 	 << M_Y <<  " amu" << endl;
   cout << " Molecular mass of Silicon:  "	 << M_Si <<  " amu" << endl;
   cout << " Molecular mass of Oxygen:   " 	 << M_O <<  " amu" << endl;


   
   cout << endl;
   cout << " ******************************************************************************** " << endl;
   cout << " *                                     RESULTS                    	            * " << endl;
   cout << " ******************************************************************************** " << endl;
   cout << endl;     

   cout << " Total mass of LYSO: " 		 << M_LYSO <<  " amu" << endl << endl;
   cout << " Mass fraction of Lutetium: " 	 << f_Lu << endl;
   cout << " Mass fraction of Yttrium:  " 	 << f_Y  << endl << endl;
   cout << " Mass fraction of Silicon:  " 	 << f_Si << endl;
   cout << " Mass fraction of Oxygen:   " 	 << f_O  << endl << endl;
   cout << " Density of LYSO:           "        << d    <<  " g/cm3" << endl;


}	
