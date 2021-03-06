# PDBMap

PDBMap is a (primarily) python command line tool and database interface designed to facilitate the visualization and analysis of genomic features in protein structures. This software includes methods for parsing and uploading structural information from the Protein Data Bank, ModBase, and custom protein structural models. It also includes methods for parsing and uploading genetic datasets in VCF and BED file formats. These datasets are then intersected using BEDTools or MySQL to create a direct mapping between each nucleotide and each associated amino acid in all associated protein structures. A schematic overview of the [PDBMap Pipeline](./docs/PDBMapPipeline.png) is provided.

Once the PDBMap database has been loaded, the PDBMap library can be imported from other projects and used to interface with and analyze genetic data within solved structures and computational models of human proteins.

## PDBMap External Dependencies

PDBMap is a portal between the fields of genetics and structural biology, and as such it relies on several (free) software packages and databases. Unfortunately, these cannot be distributed with PDBMap and must be installed separately. A complete list of the packages are provided below:

* [Python 2.7](https://www.python.org/downloads/) (We recommend [Anaconda](https://www.continuum.io/downloads))
* [MySQL](https://dev.mysql.com/downloads/os-linux.html)
* [Ensembl Core Database](http://www.ensembl.org/info/docs/webcode/mirror/install/ensembl-data.html) (use of the Ensembl public MySQL server is supported, but may result in slow runtimes)
* [Ensembl Perl API](http://www.ensembl.org/info/docs/api/api_git.html)
* [Ensembl Variant Effect Predictor (and cache)](https://github.com/Ensembl/ensembl-tools/tree/release/87/scripts) (a new beta version of VEP is now available on [github](https://github.com/Ensembl/ensembl-vep))
* [UCSF Chimera (Headless)](https://www.cgl.ucsf.edu/chimera/cgi-bin/secure/chimera-get.py?file=alpha/chimera-alpha-linux_x86_64_osmesa.bin) (for visualization)
* [DSSP](http://swift.cmbi.ru.nl/gv/dssp/) (for secondary structure and solvent accessibility)

All of these resources must be installed prior to using PDBMap. Note that all Ensembl resources should use the same genome build and all versions should match. All genomic data loaded into the database must match the Ensembl genome build. All existing resources have been built and maintained using genome build GRCh37/hg19.

```
# Installation Procedure
# Python
apt-get install anaconda2
pip install biopython
```

It is also recommended that, when possible, PDBMap be installed on a SLURM cluster. Many PDBMap tasks, like loading large numbers of protein structures, lend themselves well to parallelization. SLURM scripts for many common tasks are provided for convenience. Before launching many jobs to the cluster, check that your MySQL server is configured to manage the corresponding number of connections.

## Instantiating the PDBMap Database

To instantiate the PDBMap database, users should create a copy of DEFAULT.config with their MySQL login information and the location of all necessary resources, and then run the following command:
```
./pdbmap.py -c config/<USER>.config --create_new_db
```

Once complete, PDBMap will prompt users to install all other requried databases and resources. If you would like to install these resources later, or bring the local copies up-to-date, use:
```
./pdbmap.py -c config/<USER>.config --refresh
```
This command will download or refresh a local mirror of and/or necessary files from the following databases:
* RCSB Protein Data Bank (solved protein structures)
* ModBase (computationally predicted homology models)
* UniProt (Swiss-Prot, ID mapping, secondary-to-primary AC mapping)
* SIFTS (residue-level functional annotation and pdb-to-reference sequence alignment)
* PFAM (functional domain annotations)

The location of any of these resources may be changed. Users should update DEFAULT.config with location of all necessary resources. Note that existing copies of these datasets may be used, but the functionallity of `--refresh` may be affected. Parsing of the PDB and ModBase directory structures is also sensitive to change, so consider downloading the datasets with PDBMap and then moving the directories into a shared location; update the configuration file with the new location.

## Loading Structural Information into PDBMap
To load **only** protein structures from the Protein Data Bank into PDBMap, use
```
./pdbmap.py -c config/<USER>.config load_pdb all
```
To load **only** protein structural models from ModBase into PDBMap, use
```
./pdbmap.py -c config/<USER>.config load_model all
```
To load **all** PDB structures and ModBase models for all Swiss-Prot human proteins (recommended), use
```
./pdbmap.py -c config/<USER>.config load_unp all
```
In the database, all PDB structures receive the label `pdb` and all ModBase models receive the label `modbase` unless otherwise specified.

To load the entire PDBMap structural database in parallel using `N` SLURM jobs, update `slurm/load_pdbmap.slurm` with your SLURM account information, then use,
```
sbatch --array=0-N slurm/load_pdbmap.slurm N
```

## Loading Genomic Information into PDBMap
Any genomic dataset can be loaded into PDBMap. By default, scripts are provided to download local copies of variant data from
* The Single Nucleotide Polymorphism Database (dbSNP)
* The 1000 Genomes Project
* The Exome Sequencing Project (ESP)
* The Exome Aggregation Consortium (ExAC)
* The Catalogue of Somatic Mutations in Cancer (COSMIC)
* The GWAS Catalogue
* ClinVar
Each of these datasets can be downloaded by running the `get_<dataset>.sh` script within the corresponding directories.

To load a genomic dataset into PDBMap, use
```
./pdbmap.py -c config/<USER>.config load_data <data_file> <data_name>
OR
./pdbmap.py -c config/<USER>.config --dlabel=<data_name> load_data <data_file> [<data_file> ...]
```
Genetic datasets are often distributed by-chromosome and are thus easily parallelizable. SLURM scripts for some of the default datasets are provided and may be used a templates for designing SLURM scripts for other datasets. To load data in parallel, use
```
sbatch --array=1-24 slurm/load_exac.slurm 
```

## Intersecting Structural and Genomic Information
Once the structural and genomic datasets have each been loaded into PDBMap, they must be intersected to construct the direct mapping from nucleotide to amino acid. This can be a lengthy process, but it must only be performed once for each dataset. Once intersected, queries are very efficient, enabling large-scale, high-throughput analysis of genetic information within its protein structural context. To intersect two datasets, use
```
./pdbmap.py -c config/<USER>.config --slabel=pdb --dlabel=exac intersect
```
This command download the structural and genomic data to flat files indexed by chromosomal position, perform an intersection using `intersectBed`, and upload the results back to the database. If you are working with smaller datasets, you may consider adding the `quick` flag after `intersect`. This will perform the intersection using a MySQL join instead of `intersectBed`, which may decrease runtime. This is highly discouraged for larger datasets.

## Visualizing Genomic Information in Structure
The visualization capabilities of PDBMap are built around Chimera. Any property of a genomic dataset can be visualized by specifying the dataset and property name along with the specified gene, protein, or structure name. For example, to visualize the location of all ExAC missense variants in the first biological assembly of 2SHP, use
```
./pdbmap.py -c config/<USER>.config visualize 2SHP exac . 1
```
A new directory will be added to the `results/` directory containing several files, including a Chimera scene and an automatically generated png image of the variant-to-structure mapping. If you would instead like to color each missene variant by its minor allele frequency, 
```
./pdbmap.py -c config/<USER>.config visualize 2SHP exac maf 1
```
You can also compare the distribution to the synonymous distribution of minor allele frequencies,
```
./pdbmap.py -c config/<USER>.config visualize 2SHP exac maf.synonymous 1
```

## Navigating the PDBMap MySQL Database
The MySQL database is composed of several tables, generally organized into structural tables, genomic tables, the intersection table, and supplementary tables. 
The join order for the structure tables is:
```
Structure
          -> Chain -> Residue -> Alignment -> Transcript
Model              -> AlignmentScore
                 
```
Each table is joined on its common columns. For example, Residue and Chain are joined on matching `slabel`, `structid`, and `chain` columns.

The join order for the genomic tables is:
```
GenomicData -> GenomicConsequence -> GenomicIntersection
            -> Supplementary Tables
```
Most genetic datasets are uploaded in their original form to supplemental tables prior to being processed and uploaded into PDBMap. Joined with GenomicData on their chromosomal position, these tables allow users to incorporate additional information not supported by the default PDBMap schemas.

A detailed layout of the PDBMap database schema is provided **here**.
