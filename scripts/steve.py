#!/usr/bin/python2.7
#
# Project        : PDBMap
# Filename       : steve.py
# Author         : R. Michael Sivley
# Organization   : Center for Human Genetics Research,
#                : Department of Biomedical Informatics,
#                : Vanderbilt University Medical Center
# Email          : mike.sivley@vanderbilt.edu
# Date           : 2014-02-09
# Description    : Determines the fraction of 1000 Genomes variants who nearest
#                : neighbor in structural space differs from the nearest
#                : neighbor in genomic space.
#=============================================================================#

# Nearest neighbor (NN) algorithm specification:
# Query all PDBMap variants (point-mutations only) in sorted order: 
#   chr,start,end
#   For each variant, compare its adjacent variants, record NN
#     and its distance from the variant in a dictionary.
#
# For each structure, compute the pairwise distance matrix for all variants
#   contained within that structure.
#   For each variant in the matrix, identify the local NN and distance
#   If a global NN for that variant exists, compare with local NN
#     and overwrite if closer than global NN
#
# For each model, compute the pairwise distance matrix for all variants
#   contained within that model.
#   For each variant in the matrix, identify the local NN and distance
#   If a global NN for that variant exists, compare with local NN
#     and overwrite if closer than global NN

import numpy as np
from scipy.spatial.distance import pdist,squareform
import sys,os,csv,time,math
import MySQLdb, MySQLdb.cursors
from warnings import filterwarnings,resetwarnings
filterwarnings('ignore', category = MySQLdb.Warning)

# Hard code database credentials and connect for intermediate tables
def connect(cc=MySQLdb.cursors.Cursor):
  return MySQLdb.connect(host='gwar-dev',user='mike',
                  passwd='cheezburger',db='pdbmap_v10',
                  cursorclass=cc)

# Initialize NN dictionary
# Keyed on the target variant
# Value is a list containing two elements
# Element 0: VAR genomic tuple (name,chr,start,end)
# Element 1: GNN genomic tuple (dist,variant,chr,start,end)
# Element 2: VAR-GNN structural tuple (structid,biounit,model,chain,seqid,x,y,z)
# Element 3: GNN structural tuple (dist,structid,biounit,model,chain,seqid,x,y,z)
# Element 4: SNN genomic tuple (dist,variant,chr,start,end)
# Element 5: VAR-SNN structural tuple (structid,biounit,model,chain,seqid,x,y,z)
# Element 6: SNN structural tuple (dist,pdbid,biounit,model,chain,seqid,x,y,z)
nn = {}


####################################
## Genomic Nearest Neighbor (GNN) ##
####################################

print "Calculating nearest genomic neighbors..."

# Only consider standard chromosomes
chroms = range(1,23)
chroms.append('X')
chroms.append('Y')

# Process each chromosome separately to reduce space complexity
con = connect(cc=MySQLdb.cursors.SSCursor) # open connection
for chrom in chroms:
  q  = "SELECT DISTINCT name,chr,start,end FROM GenomicConsequence as a "
  q += "INNER JOIN GenomicIntersection as b "
  q += "ON a.gc_id=b.gc_id " # only include mapped missense SNPs
  q += "WHERE chr='chr%s' AND start=end-1 AND label='1kg' "%chrom
  q += "AND a.consequence LIKE '%missense_variant%' "
  q += "ORDER BY chr,start,end;"
  c  = con.cursor() # open cursor
  c.execute(q)
  rm2,rm1,r = None,None,None # (r-2,r-1,r)
  for r in c: # (row) operate on r-1, compare distances to r-2 and r\
    if not rm2:   # First row returned
      rm2 = r
    elif not rm1: # Second row returned
      # Assign the GNN of the first observed r 
      # to the second observed r
      rm1   = r
      rdist = abs(rm1[2]-rm2[2])
      rm1c  = list(rm1)
      rm1c.insert(0,rdist)
      nn[rm2[0]] = [tuple(rm2[1:]),tuple(rm1c),None,None,None,None,None]
    else:         # All remaining rows
      # Identify GNN of r-1
      ldist = abs(rm1[2]-rm2[2])        # Distance to left neighbor
      rdist = abs(r[2]-rm1[2])          # Distance to right neighbor
      if ldist < rdist:
        rm2c = list(rm2)
        rm2c.insert(0,ldist)             # Add distance from r-1->r-2
        nn[rm1[0]] = [tuple(rm1[1:]),tuple(rm2c),None,None,None,None,None]  # Record r-2 as NN of r-1
      else:
        rc = list(r)
        rc.insert(0,rdist)               # Add distance from r-1->r
        nn[rm1[0]] = [tuple(rm1[1:]),tuple(rc),None,None,None,None,None]    # Record r as NN of r-1
      rm2 = rm1
      rm1 = r
  c.close() # close cursor
  if r: # ensure that any rows were returned for this chromosome
    # Assign the GNN of the last observed r 
    # to the second-to-last observed r
    ldist = abs(r[2]-rm1[2])
    rm1   = list(rm1)
    rm1.insert(0,ldist)
    nn[r[0]] = [tuple(r[1:]),tuple(rm1),None,None,None,None,None]
# GNN for all variants determined
c.close() # close connection

num_vars = len(nn)
print "Number of genomic variants: %d"%num_vars

print "Done."

#######################################
## Structural Nearest Neighbor (SNN) ##
#######################################

print "Calculating nearest structural neighbors..."

# structs = []
# con = connect() # open connection
# # Query list of all (and only) PDB biological assemblies in PDBMap
# # Query from Chain for biounit, join with Structure to exclude Models
# # Join with GenomicIntersection to only include structures containing 
# # variants from this dataset
# q  = "SELECT DISTINCT a.structid,a.biounit FROM Chain as a "
# q += "INNER JOIN Structure as b "
# q += "ON a.label=b.label AND a.structid=b.pdbid "
# q += "INNER JOIN GenomicIntersection as c "
# q += "ON a.label=c.slabel AND a.structid=c.structid AND a.chain=c.chain "
# q += "INNER JOIN GenomicConsequence as d "
# q += "ON c.dlabel=d.label AND c.gc_id=d.gc_id "
# q += "WHERE a.label='uniprot-pdb' AND b.label='uniprot-pdb' "
# q += "AND c.slabel='uniprot-pdb' AND c.dlabel='1kg' "
# q += "AND d.label='1kg' AND d.start=d.end-1 "
# q += "AND d.consequence LIKE '%missense_variant%' "
# q += "AND (b.method LIKE '%nmr%' OR a.biounit>0) "
# q += "ORDER BY a.structid,a.biounit"
# c = con.cursor() # open cursor
# c.execute(q)
# structs.extend([r for r in c])
## Process all PDB-curated biological assemblies
with open('../temp/pdbmap_v10_1kg_biounits.txt','rb') as fin:
  fin.readline() # burn header
  structs = [row.strip().split('\t') for row in fin.readlines()]
num_biounits = len(structs)
print "Number of biological assemblies: %d"%num_biounits
# c.close() # close cursor
# Query list of all ModBase predicted models in PDBMap
# (ModBase recommended quality score threshold)
# Join with GenomicIntersection to only include models containing 
# variants from this dataset
# q  = "SELECT DISTINCT a.structid,a.biounit FROM Chain as a "
# q += "INNER JOIN Model as b "
# q += "ON a.label=b.label AND a.structid=b.modelid "
# q += "INNER JOIN GenomicIntersection as c "
# q += "ON a.label=c.slabel AND a.structid=c.structid AND a.chain=c.chain "
# q += "INNER JOIN GenomicConsequencef as d "
# q += "ON c.dlabel=d.label AND c.gc_id=d.gc_id "
# q += "WHERE a.label='uniprot-pdb' AND b.label='uniprot-pdb' "
# q += "AND c.slabel='uniprot-pdb' AND c.dlabel='1kg' "
# q += "AND d.label='1kg' AND d.start=d.end-1 "
# q += "AND d.consequence LIKE '%missense_variant%' "
# q += "ORDER BY a.structid,a.biounit"
# c = con.cursor() # open cursor
# c.execute(q)
# structs.extend([r for r in c])
## Process all ModBase models
with open('../temp/pdbmap_v10_1kg_models.txt','rb') as fin:
  fin.readline() # burn header
  structs += [row.strip().split('\t') for row in fin.readlines()]
num_models = len(structs)-num_biounits
print "Number of ModBase models: %d"%num_models
# c.close() # close cursor

singletons = set([])
singleton  = 0
empty      = 0
all_dup    = 0
unmapped   = 0

# Process each structure separately to reduce space complexity
for structid,biounit in structs:
  q  = "SELECT c.name,a.structid,a.biounit,a.model,a.chain,a.seqid,c.chr,c.start,c.end,a.x,a.y,a.z "
  q += "FROM Residue as a "
  q += "INNER JOIN GenomicIntersection as b "
  q += "ON a.label=b.slabel AND a.structid=b.structid AND a.chain=b.chain AND a.seqid=b.seqid "
  q += "INNER JOIN GenomicConsequence as c "
  q += "ON b.dlabel=c.label AND b.gc_id=c.gc_id "
  q += "WHERE a.label='uniprot-pdb' AND b.slabel='uniprot-pdb' "
  q += "AND b.dlabel='1kg' AND c.label='1kg' "
  q += "AND c.consequence LIKE '%missense_variant%' "
  q += "AND a.structid='%s' "%structid
  q += "AND a.biounit=%s "%int(biounit) # Consider each biological assembly
  q += "ORDER BY c.name"
  pdb_vec  = []      # Vector of structure/model information
  snp_vec  = []      # Vector of variant names
  loc_mat  = []      # Matrix of variant coordinates (3D)
  pos_vec  = []      # Vector of genomic positions
  dist_mat = [[],[]] # Matrix of pairwise variant distances (2D)
  c = con.cursor() # open cursor
  c.execute(q)
  for r in c:
    snp_vec.append(r[0])
    pdb_vec.append(list(r[1:6]))
    pos_vec.append([r[0]] + list(r[6:9]))
    loc_mat.append(list(r[-3:]))
  c.close()   # close cursor

  # Skip structures with no variants, or a a single variant
  if len(snp_vec) <= 1:
    if len(snp_vec) == 0:
      #msg = "Structure %s.%d has no variants.\n"%(structid,biounit)
      empty += 1
    else:
      #msg = "Structure %s.%d has a single variant.\n"%(structid,biounit)
      singleton += 1
      singletons.add(snp_vec[0])
    #sys.stderr.write(msg)
    continue

  # Calculate the pairwise distance matrix from the location matrix
  loc_mat  = np.array(loc_mat,dtype=np.int32)
  dist_mat = squareform(pdist(loc_mat,'euclidean'))

  # Skip if all mapped variants induce the same amino acid change
  if np.count_nonzero(dist_mat) < 1:
    #msg = "All variants in %s.%d map to the same amino acid.\n"%(structid,biounit)
    #sys.stderr.write(msg)
    all_dup += 1
    continue

  # Determine the local SNN for each variant in the structure
  for i,name in enumerate(snp_vec):
    # Determine nearest distance
    nndist = dist_mat[i][dist_mat[i]>0].min()
    # Determine variant at that distance
    nnidx  = np.where(dist_mat[i]==nndist)[0][0]
    nnname = snp_vec[nnidx]
    nnpdb  = pdb_vec[nnidx]
    nnpos  = pos_vec[nnidx]
    nnloc  = list(loc_mat[nnidx])
    if name not in nn:
      # If this variant was not observed during the GNN process
      msg = "Structural variant not observed during GNN calculation: %s"%name
      raise Exception(msg)
    # If no global SNN recorded, write local SNN
    # or overwrite if local SNN < global SNN
    if not nn[name][3] or nndist < nn[name][3][0]:
      if pos_vec[i][1] != nnpos[1]:
        nn[name][4] = tuple(['NA'] + nnpos) # if on different chromosomes
      else:
        nn[name][4] = tuple([abs(pos_vec[i][2]-nnpos[2])] + nnpos)
      nn[name][5] = tuple(pdb_vec[i]+list(loc_mat[i]))
      nn[name][6] = tuple([nndist]+nnpdb+nnloc)
    # If this variant is the genomic nearest neighbor
    # and its not recorded, or its closer,
    # record the structural locations and distance
    if nnname == nn[name][1][1]:
      if (not nn[name][3]) or nndist < nn[name][3][0]:
        nn[name][2] = tuple(pdb_vec[i]+list(loc_mat[i]))
        nn[name][3] = tuple([nndist]+nnpdb+nnloc)
con.close() # close connection

# Handle variants with no SNN, etc
for var,nns in nn.iteritems():
  if not nns[2]:
    # GNN not in any shared structure
    nn[var][2] = ['NA' for i in range(8)]
    nn[var][3] = ['NA' for i in range(9)]
  if not nns[5]:
    # No SNN
    nn[var][4] = ['NA' for i in range(5)]
    nn[var][5] = ['NA' for i in range(8)]
    nn[var][6] = ['NA' for i in range(9)]
    unmapped += 1
  elif var in singletons:
    singletons.remove(var)
    singleton -= 1

print "Done."

###############################
## Report Runtime Statistics ##
###############################

print "Reporting runtime statistics..."

print "Number of empty structures/models: %d"%empty
print "Number of structures with dup aa:  %d"%all_dup
print "Number of variants without SNN:    %d"%unmapped
print "Number of structural singletons:   %d"%singleton
# print "Sending structural singletons to stderr..."
# for s in singletons:
#   sys.stderr.write("%s\n"%s)

###################################
## Calculate the STEVE Statistic ##
###################################

print "Calculating the STEVE statistic..."

num_vars = len(nn)
# Test the GNN and SNN names for equality
diff_nn  = len([1 for nns in nn.itervalues() 
                if nns[1][1] != nns[4][1]])
# Number of null SNN
null_snn = len([1 for nns in nn.itervalues()
                if nns[4][1]=='NA'])
# Fraction of variants where GNN != SNN
steve    = float(diff_nn)/num_vars
adjsteve = float(diff_nn-null_snn)/(num_vars-null_snn-singleton)
print "\n######################\n"
print "Total vars: %d"%num_vars
print "GNN != SNN: %d"%diff_nn
print "STEVE:      %0.4f"%steve
print "NULL SNN:   %d"%null_snn
print "ADJ.STEVE:  %0.4f"%adjsteve
print ""
print "NOTE: The adjusted STEVE value does not include "
print "    : variants without structural neighbors in the "
print "    : count of differing genomic and structural "
print "    : nearest neighbors. The uncorrected STEVE value "
print "    : overestimates information gain by including "
print "    : these null values.\n"

print "Done."

#####################################
## Write nearest neighbors to file ##
#####################################

timestamp = str(time.strftime("%Y%m%d-%H"))
res_dir   = 'results/pdbmap-v9_steve_%s'%timestamp
os.system('mkdir -p %s'%res_dir)
# Write the GNN and SNN for each variant to file
with open('%s/nearest_neighbors.txt'%res_dir,'wb') as fout:
  header  = ["VAR","CHR","START","END"]
  header += ["GNN_GDIST","GNN","GNN_CHR","GNN_START","GNN_END"]
  header += ["VARG_STRUCTID","VARG_BIOUNIT","VARG_MODEL"]
  header += ["VARG_CHAIN","VARG_SEQID","VARG_X","VARG_Y","VARG_Z"]
  header += ["GNN_SDIST","GNN_STRUCTID","GNN_BIOUNIT","GNN_MODEL"]
  header += ["GNN_CHAIN","GNN_SEQID","GNN_X","GNN_Y","GNN_Z"]
  header += ["SNN_GDIST","SNN","SNN_CHR","SNN_START","SNN_END"]
  header += ["VARS_STRUCTID","VARS_BIOUNIT","VARS_MODEL"]
  header += ["VARS_CHAIN","VARS_SEQID","VARS_X","VARS_Y","VARS_Z"]
  header += ["SNN_SDIST","SNN_STRUCTID","SNN_BIOUNIT","SNN_MODEL"]
  header += ["SNN_CHAIN","SNN_SEQID","SNN_X","SNN_Y","SNN_Z"]
  fout.write("%s\n"%'\t'.join(header))
  writer = csv.writer(fout,delimiter='\t')
  for var,nns in nn.iteritems():
    row  = [var]+list(nns[0])+list(nns[1])+list(nns[2])
    row += list(nns[3])+list(nns[4])+list(nns[5])+list(nns[6])
    writer.writerow(row)

# Element 0: VAR genomic tuple (name,chr,start,end)
# Element 1: GNN genomic tuple (dist,variant,chr,start,end)
# Element 2: VAR-GNN structural tuple (structid,biounit,model,chain,seqid,x,y,z)
# Element 3: GNN structural tuple (dist,structid,biounit,model,chain,seqid,x,y,z)
# Element 4: SNN genomic tuple (dist,variant,chr,start,end)
# Element 5: VAR-SNN structural tuple (structid,biounit,model,chain,seqid,x,y,z)
# Element 6: SNN structural tuple (dist,pdbid,biounit,model,chain,seqid,x,y,z)