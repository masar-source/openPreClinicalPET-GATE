The details below should guide you through the content of this folder.


To understand the structure of the folders/files, comments about how the simulation is rnning are needed:

- Unlike other Gate useres, here I have only one macro file contains all the model commands. 
	Other users usually divide their folders into 3 folders named: mac, output and phantoms.
	mac folder content: digitizer.mac: have the electronics and signal proecessing commands
					model.mac: commands define the detetector model
					output.mac: commands define the output file 
					patientTable.mac: sometimes reffered to as object or animal table(or bed), defines the table on which the patient/object/animal is placed
					physics.mac: commands that define the physics lists
					verbose.mac: commands control how much detail the simulation prints to the console (0 = minimal, higher numbers = more detailed messages)
					vis.mac: commands control the visualisation of the model and/or the particle interactions
					world.mac: commands the define the world in which the model and all other volumes are embeded
					main.mac: contanins genral commands and commands that run the above mac files
					GateMaterials.db: should always be a standalone file and cannot be added into a mac file
	output folder content: the output files from the simulations are stored here
	phantoms folder content: contain the mac files that define the phantom which will be used for a specific test/task (e.g, scatter pahntom, sensitivty phantom, image quality phantom, etc.)
	
- The issue with their approach is that you need to, unnecessarily, create a number of folders that contain the same content mentioned above only to change 1 parameter in one single line! For example, to test the sensitivy we need to change the position (Z) of the of the table to reasonable number of steps to cover all the Field of View (FoV) length. In this case you need to copy the folder, lets say, 40 times and go to each one of them and change the translation line in each phantom, and  run each one of them independently!

Too much work, right? This is not practical, and physcisit are known to be lazy! 
So instead of all of these folders, I combined all the macs into one named "totalPETModel.mac" and wrote python scripts that can create multiple copies of the same totalPETModel.mac numberd from 1 to n (n is the number of the input position Z) then running these macs simulataneously in one click!


MY APPROACH AND FOLDER STRUCTURE:

The folders
mac_Z folder: this folder will contain the n.mac files (numbered from 1-n corresponding to each position index) created according to the positions Z listed in the xlsx files (sensitivity_measurments folder), and made by running 1-createMacForEachZ.py.

Material folder: contains the GateMaterials.db file, which is a database file contains the material definitions used in the PET model.

output folder: will contain the n.root output files (also named from 1-n ) produced by the simulations after running the script 2-runMultiCodesInSpecificRange.py which will run only a specified number of python script (found in python_script folder)

python_scripts folder: contains the n.py scripts that will run each corresponding n.mac in the mac_Z folder. each n.py will run the corresponding n.mac via docker repository with the command "opengatecollaboration/gate:8.2-docker".

sensitivity_measurments folder: contains the xlsx sheets data taken from the real measurements on the system and separate xlsx files that have the positions Z of the sensitivity tests which will be used to generate the different n.mac files found in the mac_Z folder. SensPostionsQuad35.xlsx, SensPostionsQuad72.xlsx and SensPostionsQuad86.xlsx are positions from the measurements of the different coils (35 mm, 72 mm, and 86 mm, inner diameter).


sensitivity_results folder: will contain the csv files resulted from running the analysis C script (3-analyseMultiRootSensitivity.C) that runs over the produced n.root files found in the output folder. It also contains python scripts to plot and analyse the sensitivity data.



The files
0-createCodesToRunMultiMac.py: run with "python 0-createCodesToRunMultiMac.py" (do not use the quotations!)
this script will create multiple python scripts that should run multiple n.mac files. the created scripts are named n.py, each one will run the corresponding n.mac with Gate 8.2 via docker (opengatecollaboration/gate:8.2-docker). You should specify the nymber of scripts (n.py) files it can create. However, you can do 200, it will not take space and will not affect the simulations because 2-runMultiCodesInSpecificRange.py script specifys how many scripts to run. If you have created enough n.py files to run the n.mac, you do not to run this script anymore, only once is enough.

1-createMacForEachZ.py: run with "python 1-createMacForEachZ.py" (do not use the quotations!)
this script will create multiple n.mac found in mac_Z folder which corresponds to number of positions Z specified by the sensitivity measurments. The positions Z are found in the xlsx sheets in sensitivity_measurments folder.

2-runMultiCodesInSpecificRange.py: run with "python runMultiCodesInSpecificRange.py" (do not use the quotations!)
this script will run the codes created by 1-createMacForEachZ.py and found in python_scripts folder. You should change the range of the codes it runs according to the number of n.mac created (which corresponds to the number of positions Z).

3-analyseMultiRootSensitivity.C: run with "root 3-analyseMultiRootSensitivity.C" (do not use the quotations!)
this code will loop over the the n.root files found in the output folder and calculate the ansolute sensitivty then save it as csv file (named Abs_Sensitivity_values.csv) in the sensitivity_results folder

totalPETModel.mac: The mac file that contains the whole PET model.

Files in the sensitivity_results folder:
Abs_Sensitivity_values.csv: the file contains one column of the absolute sensitivities calculated for each position Z (calculated using 3-analyseMultiRootSensitivity.C)

SensitivityPlot.xlsx: contains a table with the axial position in mm and the measured and simulated sensitivity data for each position Z. The table will be used to plot the sensitivty profile

plotSensitivity.py: plots the snesitivty profile from the table in SensitivityPlot.xlsx and save it as sensitivity_profile.png.

mard_calculation.py: will calculate the Absolute Relative Difference (ARD) for a point by point (position by position) comparison and the Mean Absolute Relative Difference (MARD) for overal comparison accross all the sensitivity profile. The data are also taken from the table in SensitivityPlot.xlsx. The resulting files are saved as ARD_by_Axial_Position.txt and MARD_Results.txt.
























