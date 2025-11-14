# PyPSA-Eur-IEI: Energy-System Model for Integrated Energy Infrastructure

This energy-system model based on the open-source [PyPSA-Eur](https://github.com/PyPSA/pypsa-eur) is the foundation of 
the report "Integrated Infrastructure Planning and 2050 Climate Neutrality: Deriving Future-Proof European Energy Infrastructures" by Fraunhofer IEG, Fraunhofer ISI and d-fine (November 2025).
It is based on release 0.10 of the open-source framework and was further extended to meet the needs of the study.
## Usage
### Download Input Data
This repository only contains the input data that was explicitly developed for this study. To access the files provided
by the open-source foundation, please download the files in the folder `data` from the following version of the code: [PyPSA-Eur (February 19th 2024)](https://github.com/PyPSA/pypsa-eur/tree/9c08af998906eec076745fae45e849bf2fc54643)
Copy these files into the `data` folder of this repository.  
Parts of the input data will be automatically retrieved using scripts from PyPSA-Eur. The data used to generate the
results for this study were downloaded on June 27th 2024.
### Setting up the Environment
Instructions on how to set up PyPSA-Eur can be found in the [documentation](https://pypsa-eur.readthedocs.io/en/latest/installation.html)
For setting up the environment, use the environment file `env/environment_pypsa_iei.yaml`. 
### Reproducing the Modelling Results
The results for the study were generated on four different main scenarios and four sensitivities. To reproduce one of 
the scenarios or sensitivities, start a run using snakemake in the terminal with  
``` snakemake -call all --configfile config/scenarios/<scenario_file_of_interest>```  
For further details on how to run a model based on PyPSA-Eur, we refer to the [open-source documentation](https://pypsa-eur.readthedocs.io/en/latest/index.html).
### Running the Evaluations
If you want to use the analysis scripts developed for this work, you first need to copy the files `country_shapes.geojson`,
`regions_offshore_elec_s_62.geojson` and `regions_onshore_elec_s_62.geojson` into a folder `scripts_analysis\shapes`.  
Then you can enter your specifications on the results you want to analyze into the script `scripts_analysis\analysis_main.py` 
and execute it to run all of the evaluations automatically.
## Contributors to the Project
For inqueries on the code, please contact wolfgang.eichhammer@isi.fraunhofer.de or info@d-fine.com.

**d-fine GmbH  
An der Hauptwache 7  
60313 Frankfurt am Main**  
Robert Beestermöller  
Caroline Blocher  
Lukas Czygan  
Linus Erdmann  
Felix Greven  
Paula Hartnagel  
Julian Hohmann  
Paul Kock  
Julius Meyer     
Ari Pankiewicz  
Anna Thünen 

**Fraunhofer-Research Institution for Energy Infrastructures and Geothermal Energy IEG  
Gulbener Straße 23  
03046 Cottbus**  
Benjamin Pfluger  
Mario Ragwitz  
Caspar Schauß  

**Fraunhofer-Research Institution for Systems and Innovation Research ISI  
Breslauerstr. 48  
76139 Karlsruhe**  
Khaled Al-Dabbas  
Sirin Alibas  
Wolfgang Eichhammer  
Tobias Fleiter  

**Fabian Neumann**  

## On Behalf of

**Agora Energiewende; Agora Think Tanks gGmbH**  
Anna-Louisa-Karsch-Straße 2  
10178 Berlin

## License

The model PyPSA-IEI developed for the study “Fraunhofer IEG/Fraunhofer ISI/d-fine (2025): Integrated Infrastructure Planning and 2050 Climate Neutrality: Deriving Future-Proof European Energy Infrastructures”, based on the PyPSA-model, is licensed under the open-source MIT license:
 
Copyright (c) 2025 Fraunhofer-Research Institution for Energy Infrastructures and Geothermal Energy IEG
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated input/output and parameter documentation files (the “Software”), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 
The modelling approach in the above mentioned study is based on PyPSA-Eur, which requires a mathematical solver for the underlying optimization problems. We acknowledge the support of Gurobi Optimization (https://www.gurobi.com) for providing a scientific license for the Gurobi Optimizer. Any user of the model will need to establish the most suitable solver in combination with the model and undertake steps to identify licence conditions for use of the appropriate optimiser.
 
The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
 
THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

