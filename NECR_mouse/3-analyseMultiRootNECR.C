//////////////////////////////////////////////////////
//                                                  //
// Analyse root output file                         //
// Original code taken from GATE benchmarkPET.C     //
// Edited by Hunor Kertesz                          //    
// Modified by Masar Almuttairi                     //
// Run: root rootAnalyseOutputSensitivity.C         //
//////////////////////////////////////////////////////

{
   gROOT->Reset();
for (int fileNumber = 1; fileNumber <= 145; ++fileNumber) {
    TString fileName = TString::Format("output/%d.root", fileNumber);
    TFile f(fileName);
    std::cout << "Processing file: " << fileName << std::endl;

   TTree *Coincidences = (TTree*)gDirectory->Get("Coincidences"); 
   TTree *Hits = (TTree*)gDirectory->Get("Hits");
   TTree *Singles = (TTree*)gDirectory->Get("Singles");
   TTree *delay = (TTree*)gDirectory->Get("delay");
   TTree *finalCoinc = (TTree*)gDirectory->Get("finalCoinc");

// Declaration of leaves types - TTree Coincidences
   Int_t           RayleighCrystal1;
   Int_t           RayleighCrystal2;
   Int_t           RayleighPhantom1;
   Int_t           RayleighPhantom2;
   Char_t          RayleighVolName1[40];
   Char_t          RayleighVolName2[40];
   Float_t         axialPos;
   Int_t           baseID1;
   Int_t           baseID2;
   Char_t          comptVolName1[40];
   Char_t          comptVolName2[40];
   Int_t           comptonCrystal1;
   Int_t           comptonCrystal2;
   Int_t           comptonPhantom1;
   Int_t           comptonPhantom2;
   Float_t         energy1;
   Float_t         energy2;   
   Int_t           eventID1;
   Int_t           eventID2;
   Float_t         globalPosX1;
   Float_t         globalPosX2;
   Float_t         globalPosY1;
   Float_t         globalPosY2;      
   Float_t         globalPosZ1;
   Float_t         globalPosZ2;
   Int_t           layerID1;
   Int_t           layerID2;
   Int_t           level1ID1;
   Int_t           level1ID2;
   Int_t           level2ID1;
   Int_t           level2ID2;
   Int_t           level3ID1;
   Int_t           level3ID2;
   Int_t           level4ID1;
   Int_t           level4ID2;
   Float_t         rotationAngle;
   Int_t           runID;
   Float_t         sinogramS;
   Float_t         sinogramTheta;
   Int_t           sourceID1;
   Int_t           sourceID2;
   Float_t         sourcePosX1;
   Float_t         sourcePosX2;
   Float_t         sourcePosY1;
   Float_t         sourcePosY2;
   Float_t         sourcePosZ1;
   Float_t         sourcePosZ2;
   Double_t        time1;
   Double_t        time2;  
   Float_t         zmin,zmax,z;

   Coincidences->SetBranchAddress("RayleighCrystal1", &RayleighCrystal1);
   Coincidences->SetBranchAddress("RayleighCrystal2", &RayleighCrystal2);
   Coincidences->SetBranchAddress("RayleighPhantom1", &RayleighPhantom1);
   Coincidences->SetBranchAddress("RayleighPhantom2", &RayleighPhantom2);
   Coincidences->SetBranchAddress("RayleighVolName1", &RayleighVolName1);
   Coincidences->SetBranchAddress("RayleighVolName2", &RayleighVolName2);
   Coincidences->SetBranchAddress("axialPos", &axialPos);
   Coincidences->SetBranchAddress("baseID1", &baseID1);
   Coincidences->SetBranchAddress("baseID2", &baseID2);
   Coincidences->SetBranchAddress("comptVolName1", &comptVolName1);
   Coincidences->SetBranchAddress("comptVolName2", &comptVolName2);
   Coincidences->SetBranchAddress("comptonCrystal1", &comptonCrystal1);
   Coincidences->SetBranchAddress("comptonCrystal2", &comptonCrystal2);
   Coincidences->SetBranchAddress("comptonPhantom1", &comptonPhantom1);
   Coincidences->SetBranchAddress("comptonPhantom2", &comptonPhantom2);
   Coincidences->SetBranchAddress("energy1", &energy1);
   Coincidences->SetBranchAddress("energy2", &energy2);
   Coincidences->SetBranchAddress("eventID1", &eventID1);
   Coincidences->SetBranchAddress("eventID2", &eventID2);
   Coincidences->SetBranchAddress("globalPosX1", &globalPosX1);
   Coincidences->SetBranchAddress("globalPosX2", &globalPosX2);
   Coincidences->SetBranchAddress("globalPosY1", &globalPosY1);
   Coincidences->SetBranchAddress("globalPosY2", &globalPosY2);
   Coincidences->SetBranchAddress("globalPosZ1", &globalPosZ1);
   Coincidences->SetBranchAddress("globalPosZ2", &globalPosZ2);
   Coincidences->SetBranchAddress("layerID1", &layerID1);
   Coincidences->SetBranchAddress("layerID2", &layerID2);
   Coincidences->SetBranchAddress("level1ID1", &level1ID1);
   Coincidences->SetBranchAddress("level1ID2", &level1ID2);
   Coincidences->SetBranchAddress("level2ID1", &level2ID1);
   Coincidences->SetBranchAddress("level2ID2", &level2ID2);
   Coincidences->SetBranchAddress("level3ID1", &level3ID1);
   Coincidences->SetBranchAddress("level3ID2", &level3ID2);
   Coincidences->SetBranchAddress("level4ID1", &level3ID1);
   Coincidences->SetBranchAddress("level4ID2", &level3ID2);
   Coincidences->SetBranchAddress("rotationAngle", &rotationAngle);
   Coincidences->SetBranchAddress("runID", &runID);
   Coincidences->SetBranchAddress("sinogramS", &sinogramS);
   Coincidences->SetBranchAddress("sinogramTheta", &sinogramTheta);
   Coincidences->SetBranchAddress("sourceID1", &sourceID1);
   Coincidences->SetBranchAddress("sourceID2", &sourceID2);
   Coincidences->SetBranchAddress("sourcePosX1", &sourcePosX1);
   Coincidences->SetBranchAddress("sourcePosX2", &sourcePosX2);
   Coincidences->SetBranchAddress("sourcePosY1", &sourcePosY1);
   Coincidences->SetBranchAddress("sourcePosY2", &sourcePosY2);
   Coincidences->SetBranchAddress("sourcePosZ1", &sourcePosZ1);
   Coincidences->SetBranchAddress("sourcePosZ2", &sourcePosZ2);
   Coincidences->SetBranchAddress("time1", &time1);
   Coincidences->SetBranchAddress("time2", &time2);

   Int_t nentries = Coincidences->GetEntries();
   Int_t ndelays = delay->GetEntries();   
   Int_t nbytes = 0, nbytesdelay = 0, nrandom = 0, nscatter = 0, ntrue = 0;

   for (Int_t i=0; i<nentries;i++) {
     nbytes += Coincidences->GetEntry(i);

     if (eventID1 != eventID2) {
       ++nrandom;
     } else {
       if (eventID1 == eventID2 && comptonPhantom1 == 0 && comptonPhantom2 == 0 &&
           RayleighPhantom1 == 0 && RayleighPhantom2 == 0) {
         ntrue++;
       } else {
         nscatter++;
       }
     }
   }

   float nprompt = ntrue + nscatter + nrandom;
   float NECR = ntrue * (ntrue / nprompt);

   std::string filePath = "NECR_results/NECR_valuessss.csv";
   std::ifstream inFile(filePath);
   bool isEmpty = inFile.peek() == std::ifstream::traits_type::eof();
   inFile.close();

   std::ofstream outFile(filePath, std::ios::app); 
   if (isEmpty) {
     outFile << "Trues (kcps) \t Randoms (kcps) \t Scattered (kcps) \t Prompts (kcps) \t NECR (kcps) \n";
   }
   outFile << ntrue*0.01 << '\t' << nrandom*0.01 << '\t' << nscatter*0.01 << '\t' << nprompt*0.01 << '\t' << NECR*0.01  << std::endl;
   outFile.close();

   std::ofstream txtFile("NECR_results/NECR_values1.txt", std::ios::app);
   txtFile << ntrue*0.01 << '\t' << nrandom*0.01 << '\t' << nscatter*0.01 << '\t' << nprompt*0.01 << '\t' << NECR*0.01  << std::endl;
   txtFile.close();

   std::ofstream fakeXlsx("NECR_results/NECR_values1.xlsx", std::ios::app);
   fakeXlsx << ntrue*0.1 << '\t' << nrandom*0.1 << '\t' << nscatter*0.1 << '\t' << nprompt*0.1 << '\t' << NECR*0.1  << std::endl;
   fakeXlsx.close();

   cout << endl << endl;     
   cout << " ****************************************************************** ************* " << endl;
   cout << " *                                                                              * " << endl;
   cout << " *                          GATE PET RESULTS ANALYSIS                           * " << endl;
   cout << " *                                                                              * " << endl;
   cout << " ******************************************************************************** " << endl;
   cout << endl << endl;     
   cout << " There are " << ndelays << " delayed coincidences" << endl;
   cout << " There are " << ntrue << " true unscattered coincidences" << endl;
   cout << " There are " << nrandom << " random coincidences" << endl;
   cout << " There are " << nscatter << " scattered coincidences" << endl;
   cout << "  ==> there are " << nentries << " coincidences (true, scattered, and random)" << endl;   
   cout << "  ==> global scatter fraction: = " << (float)nscatter/(float)(nentries-nrandom)  << endl << endl;
   cout << "  ==> The Noise Equivalent Count Rate is: NECR = " << NECR << endl << endl << endl << endl;

}
}

