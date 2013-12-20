#!/usr/bin/python27

# Command Line Arguments:
# calc_fst.r pop-id-map pedmap krange snp-groups

import sys,os,csv,subprocess,math
from itertools import combinations,product

def main():

  ## Check cmd line arguments
  if len(sys.argv) < 2:
    print "usage: \n\tcalc_fst.py pop-id-map pedmap krange snp-groups snp-pdb-loc"
    sys.exit(1)

  ## Read cmd line arguments
  pop_id_map = sys.argv[1]
  pedmap     = sys.argv[2]
  kbounds = (0,0)
  if len(sys.argv) > 2:
    kbounds    = sys.argv[3].split(':')
  krange = range(int(kbounds[0]),int(kbounds[1])+1)
  snp_groups = None
  if len(sys.argv) > 3:
    snp_groups = sys.argv[4]

  ## Preprocess the pedmap for hierfstat if necessary
  if not os.path.isfile("%s-tab1234.ped"%pedmap):
    preprocess_pedmap(pedmap)

  ## Read the populations
  pop_id_dict = read_pop(pop_id_map)

  ## Read all SNPs, and their chr,bp
  snp_map = read_map(pedmap)

  ## Remove SNPs with MAF == 0.0
  snp_map = qc_freq(snp_map,pedmap)

  ## Read SNP groups if specified
  if snp_groups:
    group_snp_dict,snp_loc,snp_list = read_groups(snp_groups,snp_map)
  # Only group-associated SNPs present in the snp_map are recorded
  # As such, snp_list holds the union of the pedmap and pdbmap SNPs

  ## Compute pairwise distance and LD (R^2) for all SNPs
  snp_ld,snp_bp_dist = calc_ld_dist(pedmap,snp_list)

  ## Compute pairwise structural distance for all SNPs
  snp_3d_dist = calc_3d_dist(snp_loc)

  ## Compute the global and individual Fst scores, initialize snp_fstat
  snp_fstat = calc_global_fst(snp_list,pop_id_map,pedmap)
  if 1 in krange: krange.remove(1) # k=1 implicitly calculated

  ## Compute Fst for k-wise tuples (k > 1), update snp_fstat
  # snp_fstat = calc_kwise_fst(snp_fstat,pop_id_map,pedmap,krange,snp_groups,group_snp_dict)
  snp_fstat = calc_kwise_fst(snp_fstat,pop_id_map,pedmap,krange,snp_list)

  ## Aggregate all the measurements and statistics
  aggregate_stats(snp_bp_dist,snp_3d_dist,snp_ld,snp_fstat)

def aggregate_stats(snp_1d_dist,snp_3d_dist,snp_ld,snp_fst):
  # all snps with 3d structural information and a partner
  snps = snp_3d_dist.keys()
  print "rs# Fst(ind) Fst(n(1d)) Fst(n(3d)) LD(n(1d)) LD(n(3d))"
  for snp in snps:
    ind_fst = snp_fst[snp][1]
    # get the snp name of the nearest snp in 1d and 3d
    nearest1d = min(snp_1d_dist[snp],key=snp_1d_dist[snp].get)
    # for all partner snps B, find shortest distance b/w A and B
    # and select the A->B pair with the shortest distance overall
    nearest3d = min([(min(snp_3d_dist[snp][snpb][0]),snpb) for snpb in snp_3d_dist[snp]])[1]
    # Lookup Fst for nearest partners
    fstn1d = snp_fst[snp][2][(nearest1d,)]
    fstn3d = float("NaN") if nearest3d == "NA" else snp_fst[snp][2][(nearest3d,)]
    # Lookup LD for nearest partners
    ldn1d  = snp_ld[snp][nearest1d]
    ldn3d  = float("NaN") if nearest3d == "NA" else snp_ld[snp][nearest3d]
    print "%s %f %f %f %f %f"%(snp,ind_fst,fstn1d,fstn3d,ldn1d,ldn3d)

def read_pop(pop_id_map):
  with open(pop_id_map,'rb') as fin:
    pop_id_dict = {}
    # population : [sample_id,...]
    reader = csv.reader(fin,delimiter='\t')
    for row in reader:
      pop_id_dict.setdefault(row[1],[]).append(row[0])
  populations = pop_id_dict.keys()
  print "\nPopulations: %s"%" ".join([str((i,pop)) for i,pop in enumerate(populations)])
  return pop_id_dict

def read_map(pedmap):
  snp_map = {}
  map_file = "%s-tab1234.map"%pedmap
  with open(map_file,'rb') as fin:
    reader = csv.reader(fin,delimiter='\t')
    for row in reader:
      # SNP name -> chr,bp
      snp_map[row[1]] = (row[0],row[3])
  return snp_map

def qc_freq(snp_map,pedmap):
  try:
    cmd = "plink --file %s --freq --noweb"%pedmap
    p = subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    out,err = p.communicate() # ensure process has finished
    with open("plink.frq",'rb') as fin:
      header = fin.readline()
      for line in fin:
        row = line.split()
        snp,frq = row[1],float(row[4])
        if frq < 0.0000001: # "zero"
          del snp_map[snp]
    return snp_map
  except: raise
  finally:
    os.system("rm -f plink.*") # remove plink output files

def read_groups(snp_groups,snp_map):
  snp_loc = {}
  all_snps = set([])
  union_snps  = set([])
  if snp_groups:
    group_snp_dict = {}
    # pdbid : [snp,...]
    with open(snp_groups,'rb') as fin:
      reader = csv.reader(fin,delimiter='\t')
      for row in reader:
        all_snps.add(row[0])
        # Only read SNPs present in the pedmap
        if row[0] in snp_map:
          # Only read unique SNPs (intentional duplication in file)
          if row[0] not in group_snp_dict.setdefault(row[1],[]):
            group_snp_dict[row[1]].append(row[0])
          # Record the SNP (qualified by pdbid and chain) 3D location
          snp_loc.setdefault(row[0],{})[(row[1],row[2])] = [float(x) for x in row[3:]]
          union_snps.add(row[0])
    groups = group_snp_dict.keys()
    print "\nGroups: %s"%" ".join(groups)
    print "\n%d of %d group SNPs found in pedmap with MAF > 0.0."%(
              len(union_snps),len(all_snps))
  # Pull those SNPs 
  snp_list = list(union_snps)
  snp_list.sort()
  return group_snp_dict,snp_loc,snp_list

def calc_ld_dist(pedmap,snp_list):
  snp_bp_dist  = {}
  snp_ld = {}
  try:
    # cmd = "plink --file %s --r2 --ld-window-kb 500000 --noweb"%pedmap
    cmd = "plink --file %s --r2 --ld-window 250000000 --ld-window-kb 250000 --ld-window-r2 0.0 --noweb"%pedmap
    p = subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    out,err = p.communicate() # ensure process has finished
    with open("plink.ld",'rb') as fin:
      header = fin.readline()
      # CHR_A BP_A SNP_A CHR_B BP_B SNP_B R2
      for line in fin:
        row = line.split()
        # Only include pedmap-pdbmap union SNPs
        # and if the SNPs are on the same chromosome
        if row[2] in snp_list and row[5] in snp_list and row[0]==row[3]:
          row[1],row[4],row[6] = float(row[1]),float(row[4]),float(row[6])
          # Distances
          snp_bp_dist.setdefault(row[2],{})[row[5]] = math.fabs(row[4]-row[1])
          snp_bp_dist.setdefault(row[5],{})[row[2]] = math.fabs(row[4]-row[1])
          # LD (R^2)
          snp_ld.setdefault(row[2],{})[row[5]] = row[6]
          snp_ld.setdefault(row[5],{})[row[2]] = row[6]

    snpAs = snp_bp_dist.keys()
    for snpA in snpAs:
      snpBs = snp_bp_dist[snpA].keys()
      # for snpB in snpBs:
      #   print "%s %s -> GD=%d LD=%f"%(snpA,snpB,snp_bp_dist[snpA][snpB],snp_ld[snpA][snpB])

    print "# LD SNPs:",len(snp_ld)
    print "# 1D SNPs:",len(snp_bp_dist)
    return snp_ld,snp_bp_dist
  except: raise
  finally:
    os.system("rm -f plink.*") # remove plink output files

def calc_global_fst(snp_list,pop_id_map,pedmap):
  snp_fstat = {}
  tup = snp_list
  # Write N-tuples to temp file
  tempfile = "%d.temp"%multidigit_rand(5)
  try:
    with open(tempfile,'wb') as fout:
      fout.write(' '.join(tup))
    # Calculate Fst
    cmd = ["calc_fst.r",pop_id_map,pedmap,tempfile]
    p = subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    out,err = p.communicate()
    parser = string_parser(out.split('\n'))
    global_fst,ind_fst,pop_freqs = parse_all(parser)
    # Collapse Fst and Frequencies into one dictionary
    snp_popgen = {}
    print "# Fst scores:",len(ind_fst)
    print "# Frequencies:",len(pop_freqs)
    keys = pop_freqs.keys()
    keys.sort()
    for key in keys:
      snp_popgen[key] = (ind_fst[key],pop_freqs[key])

    snps = snp_popgen.keys()
    snps.sort()
    for snp in snps:
      # if not math.isnan(snp_popgen[snp][0]):
      # print "%s\t%f"%(snp,snp_popgen[snp][0])
      snp_fstat[snp] = {1:snp_popgen[snp][0]}
    print "# Fst SNPs:",len(snp_fstat)
    print "Global Fst: ",global_fst
    return snp_fstat # not necessary, but improves clarity
  except: raise
  finally:
    os.system("rm -f %s"%tempfile) # delete temp file

def calc_kwise_fst(snp_fstat,pop_id_map,pedmap,krange,snp_list=None,snp_groups=None,group_snp_dict=None):
  tuple_fstat = {}

  for k in krange:

    # If these have been computed before, load k-wise Fst from file
    if os.path.isfile('%s_%d-tuple.fst'%(pedmap,k)):
      print "Loading %d-wise Fst from log..."%k
      with open('%s_%d-tuple.fst'%(pedmap,k),'rb') as fin:
        reader = csv.reader(fin,delimiter='\t')
        for row in reader:
          snp_fstat[row[0]].setdefault(k,{})[tuple(row[2:])] = float(row[1])
      continue # to next k

    # Generate k-tuples
    print "Calculating tuples for k=%d..."%k
    combns = []
    if snp_groups:
      for group in group_snp_dict.iterkeys():
        new_combns = [x for x in combinations(group_snp_dict[group],k)]
        combns.extend(new_combns)
    elif snp_list:
        combns = [x for x in combinations(snp_list,k)]
    else: raise Exception("Must provide snp_list or snp_groups")

    # Write the k-tuples to temp file
    tempfile = "%d.temp"%multidigit_rand(5)
    try:
      with open(tempfile,'wb') as fout:
          writer = csv.writer(fout,delimiter=' ')
          for combn in combns:
            writer.writerow(combn)

      # Calculate Fst
      cmd = ["calc_fst.r",pop_id_map,pedmap,tempfile]
      p = subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
      out,err = p.communicate()
      if err:
        print "Errors:"
        print err
      parser = string_parser(out.split('\n'))
      tuple_fstat[k] = parse_tuples(parser,combns)
    except: raise
    finally:
      os.system("rm -f %s"%tempfile)
  
  ks = tuple_fstat.keys()
  ks.sort()
  for k in ks:
    with open('%s_%d-tuple.fst'%(pedmap,k),'wb') as fout:
      print "%d-tuples:"%k
      tups = tuple_fstat[k].keys()
      tups.sort()
      for tup in tups:
        # if not math.isnan(tuple_fstat[k][tup][6]):
        # print "%s\t%f"%('\t'.join(tup),tuple_fstat[k][tup][6])
        fst = tuple_fstat[k][tup][6]
        for snp in tup:
          partners = tuple([x for x in tup if x!=snp])
          if snp in snp_fstat:
            snp_fstat[snp].setdefault(k,{})[partners] = fst
            fout.write("%s\t%f\t%s\n"%(snp,fst,"\t".join(partners)))
  print set([str(len([x for x in snp_fstat[snp][2]])) for snp in snp_fstat])
  return snp_fstat

def calc_3d_dist(snp_loc):
  snp_3d_dist = {}
  snp_pairs = [x for x in combinations(snp_loc.keys(),2)]
  for snp_pair in snp_pairs:
    snpA_locs = snp_loc[snp_pair[0]]
    snpB_locs = snp_loc[snp_pair[1]]
    # only retain pairs if the pdbids match
    loc_pairs = [x for x in product(snpA_locs.iteritems(),snpB_locs.iteritems()) if x[0][0][0]==x[1][0][0]]
    for loc_pair in loc_pairs:
      # (snpA,pdb-chain,(x,y,z)) , (snpB,pdb-chain,(x,y,z))
      xd = loc_pair[0][1][0]-loc_pair[1][1][0]
      yd = loc_pair[0][1][1]-loc_pair[1][1][1]
      zd = loc_pair[0][1][2]-loc_pair[1][1][2]
      d  = math.sqrt(xd*xd + yd*yd + zd*zd)
      # snpA -> snpB -> (distance,loc_pair)
      snp_3d_dist.setdefault(snp_pair[0],{})
      snp_3d_dist[snp_pair[0]].setdefault(snp_pair[1],[])
      # Add distance, keep locations for reference
      snp_3d_dist[snp_pair[0]][snp_pair[1]].append((d,loc_pair))
      # print "dist(%s,%s) = %2.3f via %s:%s->%s:%s"%(snp_pair[0],snp_pair[1],d,
      #   loc_pair[0][0][0],loc_pair[0][0][1],loc_pair[1][0][0],loc_pair[1][0][1])
  lonely_snps = [snp for snp in snp_loc if snp not in snp_3d_dist]
  # Dummy code an NA partner and NaN distance for SNPs with no 3D partners
  for snp in lonely_snps:
    snp_3d_dist[snp] = {"NA":[(float("NaN"),None)]} 
  print "# 3D SNPs:",len(snp_3d_dist)
  return snp_3d_dist

def parse_all(parser):
  for line in parser:
    line = line.strip()
    if not line:
      continue
    if line[0] == "$":
      pop_freqs = parse_freq(parser,line[1:])
    elif line == "Fst":
      ind_fst = parse_fst(parser)
    elif line.split(' ')[0] == "Ho":
      global_fstats = parse_overall(parser)
  return global_fstats,ind_fst,pop_freqs

def parse_tuples(parser,combns):
  results = {}
  combn_count = 0
  for line in parser:
    line = line.strip()
    if not line or line == "Fst":
      continue
    elif line == "##":
      break
    elif line.split(' ')[0] == "Ho":
      continue
    if len(line.split()) == 1:
      results[combns[combn_count]] = [float("NaN")]*11
    else:
      results[combns[combn_count]] = [float(x) for x in line.split()]
    combn_count += 1
  # Ho Hs Ht Dst Htp Dstp Fst Fstp Fis Fis Dest
  return results

def parse_overall(parser):
  for line in parser:
    line = line.strip()
    if not line or line == "Fst":
      continue
    elif line == "##":
      break
    elif line.split(' ')[0] == "Ho":
      continue
    results = [float(x) for x in line.split(' ')]
  # Ho Hs Ht Dst Htp Dstp Fst Fstp Fis Fis Dest
  return results

def parse_fst(parser):
  results = {}
  for line in parser:
    line = line.strip()
    if not line:
      continue
    elif line == "##":
      break
    snp_name,fst = line.split()
    snp_name  = snp_name
    results[snp_name] = float(fst)
  return results

def parse_freq(parser,snp_name):
  results = {}
  pop_freqs = {}
  snp_name = snp_name.replace('.',':')
  for line in parser:
    line = line.strip()
    if not line:
      continue
    elif line == "##":
      if pop_freqs:
        # save current SNP
        results[snp_name] = pop_freqs
      break
    elif line[0] == '$':
      if pop_freqs:
        # save current SNP
        results[snp_name] = pop_freqs
      # begin parsing next SNP
      snp_name  = line[1:].replace('.',':')
      pop_freqs = {}
    elif line[0] == 'x':
      continue
    else:
      line      = line.strip()
      pop_freqs[line[0]] = line[1:].strip().split(' ')
  if pop_freqs:
    # save current SNP
    results[snp_name] = pop_freqs
  return results

def string_parser(content):
  for line in content:
    yield line

def tup_eq(a,b):
  return all(x in b for x in a) and all(x in a for x in b)

def preprocess_pedmap(pedmap):
  os.system("""plink --noweb --file %s --allele1234 --tab --recode --out %s-tab1234"""%(pedmap,pedmap))
  os.system("""sed -e 's/[ ]//g' %s-tab1234.ped > %s-tab1234TEMP.ped"""%(pedmap,pedmap))
  os.system("""mv -f %s-tab1234TEMP.ped %s-tab1234.ped"""%(pedmap,pedmap))

# Support function for temp files
def multidigit_rand(digits):
  import random
  randlist = [random.randint(1,9) for i in xrange(digits)]
  multidigit_rand = int(''.join([str(x) for x in randlist]))
  return multidigit_rand

if __name__ == "__main__":
  main()