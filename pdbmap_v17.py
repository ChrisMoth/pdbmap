#!/usr/bin/python27

# This script takes a configuration file as input, specifying the PDB archive,
# the database information in which to store the PDB->Genome mappings,
# and booleans for whether to create a new database or to identify human
# homologues for non-human protein structures.

## ---- Experimental Simple Alignment and Scoring ---- ##
from Bio import pairwise2
from Bio.SubsMat import MatrixInfo as matlist
## --------------------------------------------------- ##

import argparse,ConfigParser,traceback
import os,sys,csv,time,subprocess,gzip,string
import sqlite3,MySQLdb
from warnings import filterwarnings	# Disable MySQL warnings
filterwarnings('ignore',category=MySQLdb.Warning)
filterwarnings('ignore',"Unknown table.*")

# Setup the Config File Parser
conf_parser = argparse.ArgumentParser(add_help=False)
conf_parser.add_argument("-c", "--conf_file",
help="Specify config file", metavar="FILE")
args, remaining_argv = conf_parser.parse_known_args()
defaults = {
	"dbhost" : "localhost",
	"dbname" : "pdbmap",
	"dbuser" : "user",
	"dbpass" : "pass",
	"pdb_dir" : "./pdb",
	"map_dir" : "./maps",
	"disable_human_homologue" : False,
	"create_new_db" : False,
	"force" : False,
	"pdbid" : "",
	"species" : "",
	"unp" : "",
	"speclist" : "",
	"transmap" : ""
	}
if args.conf_file:
	config = ConfigParser.SafeConfigParser()
	config.read([args.conf_file])
	defaults = dict(config.items("Genome_PDB_Mapper"))

# Setup the Command Line Parser
parser = argparse.ArgumentParser(parents=[conf_parser],description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
defaults['disable_human_homologue'] = ('True' == defaults['disable_human_homologue'])
defaults['create_new_db'] = ('True' == defaults['create_new_db'])
parser.set_defaults(**defaults)
parser.add_argument("--dbhost", help="Database hostname")
parser.add_argument("--dbuser", help="Database username")
parser.add_argument("--dbpass", help="Database password")
parser.add_argument("--dbname", help="Database name")
parser.add_argument("--pdb_dir", help="Directory containing PDB files")
parser.add_argument("--map_dir", help="Directory to save pdbmap BED file")
parser.add_argument("--disable_human_homologue", action='store_true', help="Disable mapping from non-human PDBs to human homologues")
parser.add_argument("--create_new_db", action='store_true', help="Create a new database prior to uploading PDB data")
parser.add_argument("-f", "--force", action='store_true', help="Force configuration. No safety checks.")
parser.add_argument("--pdbid", help="Force pdbid")
parser.add_argument("--species", help="Force species")
parser.add_argument("--unp", help="Force unp")
parser.add_argument("--speclist", help="Species code -> species map file")
parser.add_argument("--transmap", help="UniProt ID -> EnsEMBL transcript map file")


def main():
	"""Map each PDB to its genomic coordinates and upload to the specified database"""

	# If a new database needs to be created, create one.
	if args.create_new_db:
		create_new_db(args.dbhost,args.dbuser,args.dbpass,args.dbname)
		print "Database created."
		sys.exit(0)

	# Identify all PDB structures in pdb_dir
	if os.path.isdir(args.pdb_dir):
		pdb_files = ['%s/%s'%(args.pdb_dir,pdb_file) for pdb_file in os.listdir(args.pdb_dir)]
	else:
		pdb_files = [args.pdb_dir]
	pdbs   = dict((os.path.basename(pdb_file).split('.')[0][-4:].upper(),pdb_file) for pdb_file in pdb_files)

	# Load each PDB structure
	pdb_count     = 0
	skipped_count = 0
	mapped_count  = 0
	print "\n%d PDB file(s) found."%len(pdb_files)
	new_pdbs = get_new_pdbs(pdbs,args.dbhost,args.dbuser,args.dbpass,args.dbname)
	print "%d/%d PDB file(s) not found in database."%(len(new_pdbs),len(pdb_files))

	# Success profiler
	t_elapsed_success = 0
	# Failure profiler
	t_elapsed_fail    = 0

	new_pdbs.sort()	# For easier post-analysis
	for pdb_id,pdb_file in new_pdbs:
		# print "\nProcessing PDB %s..."%pdb_id
		try:
			t0 = time.time() # Profiler
			status,num_matches = load_pdb(pdb_id,pdb_file)
			if status:
				skipped_count += 1
				t_elapsed_fail += time.time()-t0 # Profiler
			else:
				pdb_count += 1
				t_elapsed_success += time.time()-t0 # Profiler
			mapped_count += num_matches
		except (KeyboardInterrupt,SystemExit):
			print("\nExiting...")
			sys.exit(0)
		except:
			tb = traceback.format_exc().replace('\n','::')
			print "\nProcessing PDB %s..."%pdb_id
			print("\tSkipping:")
			sys.stdout.write("\tPDB %s could not be processed.\n"%pdb_id)
			sys.stdout.write("\t%s\n\n"%tb)
			sys.stderr.write("%s was removed for an unhandled exception: %s\n"%(pdb_id,tb))
			skipped_count += 1
			os.system('rm -f %s.tab'%pdb_id)
			t_elapsed_fail += time.time()-t0 # Profiler
	

	# Success profiler
	if pdb_count > 0:
		t_average_success = t_elapsed_success / pdb_count
	else:
		t_average_success = 0
	if skipped_count > 0:
		t_average_fail = t_elapsed_fail / skipped_count
	else:
		t_average_fail = 0
	t_elapsed = t_elapsed_fail + t_elapsed_success
	print "\n#----------------------------------#\n"
	print "Number of PDBs skipped: %d"%skipped_count
	print "Number of PDBs processed: %d"%pdb_count
	print "Number of PDBs mapped: %d"%mapped_count
	print "Total execution time: %f"%t_elapsed
	print "Average execution time for successful PDB: %2.2f"%t_average_success
	print "Average execution time for skipped PDB: %2.2f"%t_average_fail
	print "Building GenomePDB..."
	con = MySQLdb.connect(host=args.dbhost,user=args.dbuser,passwd=args.dbpass,db=args.dbname)
	c = con.cursor()
	c.execute("SELECT * FROM GenomePDB LIMIT 1")
	res = c.fetchone()
	if not res: # not yet generated
		c.execute("CALL build_GenomePDB();")
	else: # adding to existing
		for pdb_id,pdb_file in new_pdbs:
			pdb_id = pdb_id if not args.pdbid else args.pdbid
			c.execute("CALL update_GenomePDB('%s')"%pdb_id)
	con.close() # b/c it may have timed out already anyway
	print "Generating BED file for %s..."%args.dbname
	c = con.cursor()
	c.execute("SELECT * FROM GenomePDB");
	with open("%s%s.bed"(args.map_dir,args.dbname)) as fin:
		writer = csv.writer(fin,delimiter='\t')
		writer.writerows(c.fetchall())
	con.close()
	print "\nComplete."

def sqlite_init():
	"""Initializes a temporary SQLite instance for local PDB->Genome Mapping"""
	con = sqlite3.connect(':memory:')
	c = con.cursor()
	c.execute("CREATE TABLE chains (chain VARCHAR(10),unp VARCHAR(20),pdb VARCHAR(50),pdbstart INT,offset INT,species VARCHAR(50),PRIMARY KEY(chain))")
	c.execute("CREATE TABLE coords (chain VARCHAR(10),serialnum INT,seqres INT,aa3 VARCHAR(3), aa1 VARCHAR(1),x DOUBLE,y DOUBLE,z DOUBLE,PRIMARY KEY(chain,serialnum))")
	c.execute("CREATE TABLE seqadv (chain VARCHAR(10),seqres INT,aa3 VARCHAR(3),conflict VARCHAR(20),PRIMARY KEY(chain,seqres))")
	con.commit()
	return c,con

def load_pdb(pdb_id,pdb_file):
	"""Parse a PDB file and store the important information into SQLite"""
	global transmap

	# Initialize a temporary SQLite database
	c,con = sqlite_init()

	# Load all information from the PDB file
	# Use gzip if the files appear to be gzipped
	# print "\tParsing info from %s..."%pdb_file
	if os.path.splitext(pdb_file)[-1] == '.gz':
		fin = gzip.open(pdb_file,'r')
	else:
		fin = open(pdb_file,'r')

	# Assign all forced variables
	pdb_id = pdb_id if not args.pdbid else args.pdbid
	print

	species         = []
	experiment_type = None
	best_model      = 1
	cur_model       = 1
	header_read     = False
	for line in fin:
		field = line[0:6].strip()
		code  = line[7:10]
		# print field
		# print best_model
		# print cur_model
		if field == "REMARK" and code[0] == "2":
			if not experiment_type:
				experiment_type   = read_experiment_type(line,c)
			elif experiment_type == "NMR" and not best_model:
				best_model = read_best_model(line,c)
		elif field == "SOURCE" and line[11:30] == "ORGANISM_SCIENTIFIC":
			species.append(read_species(line))
		# elif field == "SOURCE" and line[11:20] == "SYNTHETIC":
		# 	species.append("synthetic")
		elif field == "MODEL":
			cur_model = int(line[10:14])
		elif field == "DBREF":
			if check_species(species) and not args.force:
				fin.close()
				sys.stderr.write("%s was removed for failing the species check.\n"%pdb_id)
				return 1,0
			if read_dbref(line,c,pdb_id) and not args.force:
				sys.stderr.write("%s was removed because it contains an insertion or deletion.\n"%pdb_id)
		elif field == "SEQADV":
			read_seqadv(line,c)
		elif field == "ATOM" and cur_model == best_model:
			read_atom(line,c)
	con.commit()

	# Check that required fields have some information
	c.execute("SELECT * FROM chains")
	if not c.fetchone():
		if not args.force:
			sys.stderr.write("%s was removed because no chains were parsed.\n"%pdb_id)
			return 1,0
		else:
			print "Forcing chain information: chain=A,unp=%s,pdbid=%s,pdbstart=0,offset=0,species=%s"%(args.unp,args.pdbid,args.species)
			c.execute("INSERT INTO chains VALUES (?,?,?,?,?,?)",('A',args.unp,args.pdbid,0,0,args.species))
	c.execute("SELECT * FROM coords")
	if not c.fetchone():
		sys.stderr.write("%s was removed because no atoms were parsed.\n"%pdb_id)
		return 1,0

	print "\n\nProcessing PDB %s..."%pdb_id

	print("\tExperiment type: %s"%experiment_type)
	if experiment_type == "NMR":
		print("\tBest Model: %d"%best_model)
	c.execute("SELECT * FROM chains")
	print "\t%d chains"%len(c.fetchall())
	c.execute("SELECT * FROM coords")
	print "\t%d atoms"%len(c.fetchall())
	fin.close()

	# This was removed when alignment was added
	# Even if a mutation is known, it needs to be left in the sequence
	# so that alignment tools have the proper indices in the peptide sequence.
	# 
	# Remove any residues with conflicts not explicitly allowed
	# print("\tRemoving SEQADV conflicts...")
	# c.execute("SELECT chain,seqres,conflict FROM seqadv WHERE conflict!='ENGINEERED MUTATION' AND conflict!='MODIFIED RESIDUE'")
	# for chain,seqres,conflict in c.fetchall():
	# 	print("\t\tSEQADV %s,%s removed. Conflict: %s"%(chain,seqres,conflict))
	# 	c.execute("DELETE FROM coords WHERE chain=? AND seqres=?",(chain,seqres))
	# con.commit()

	# Write data to tabular for MySQL upload
	write_pdb_data(pdb_id,c,con)

	# Pull local processing information
	c.execute("SELECT unp,chain,species FROM chains")
	unp_chains = c.fetchall()
	c.execute("SELECT chain,seqres FROM seqadv WHERE conflict='ENGINEERED MUTATION' OR conflict='MODIFIED RESIDUE'")
	seqadv_protected = c.fetchall()
	con.close()	# Close the local SQLite connection

	# Create tabulars for the genomic data
	with open("%s_GenomicCoords.tab"%pdb_id,"w") as fout:
		fout.write("transcript\tgene\tseqres\taa1\tstart\tend\tchr\tstrand\n")
	with open("%s_PDBTranscript.tab"%pdb_id,"w") as fout:
		fout.write("pdb\tchain\ttranscript\thomologue\n")
	for unp_chain in unp_chains:
		unp = str(unp_chain[0]).upper()
		chain = str(unp_chain[1])
		species = str(unp_chain[2])
		try:
			exit_code = 0
			# Use UniParc to find candidate transcripts
			# UniParc results will be written first, and be chosen over Ensembl-
			# identified transcripts in a tie.
			transcripts = transmap.get(unp,[])
			for transcript,id_type in transcripts:
				if species=="homo_sapiens":
					print "\tLoading -> %s.%s (%s), %s -> %s"%(pdb_id,chain,unp,species,transcript)
					exit_code += subprocess.call(["lib/transcript_to_genomic.pl",pdb_id,chain,unp,species,transcript])
				else:
					ung = unp2ung(unp)
					if not ung:
						sys.stdout.write("No UniGene entry found -> pdb: %s, chain: %s, unp: %s, species: %s"%(pdb_id,chain,unp,species))
						sys.stderr.write("%s was removed because %s matched no UniGene entry.\n"%(unp,pdb_id))
						return 1,0
					else:
						# Use Ensembl to find candidate homologue transcripts
						print "\tSearching for human homologues -> pdb: %s, chain: %s, unp: %s, ung: %s, species: %s"%(pdb_id,chain,unp,ung,species)
						exit_code += subprocess.call(["lib/unigene_to_homologue_genomic.pl",pdb_id,chain,ung,species])
			# Use Ensembl to find candidate transcripts
			exit_code += subprocess.call(["lib/protein_to_genomic.pl",pdb_id,chain,unp,species])
			if exit_code:
				print("\tSkipping:")
				sys.stdout.write("\tPerl returned a non-zero exit status.\n")
				os.system('rm -f %s.tab'%pdb_id)
				sys.stderr.write("%s was removed because a Perl subscript crashed.\n"%pdb_id)
				return 1,0
		except KeyboardInterrupt:
			if raw_input("\nContinue to next PDB? (y/n):") == 'n':
				raise KeyboardInterrupt
			print("\tSkipping:")
			print("\tCanceled by user.")
			sys.stderr.write("%s was removed because the user canceled the processing\n"%pdb_id)
			# Clean up any temporary files
			os.system('rm -f %s_PDBTranscript.tab'%pdb_id)
			os.system('rm -f %s_Alignment.tab'%pdb_id)
			os.system('rm -f %s_AlignmentScores.tab'%pdb_id)
			os.system('rm -f %s.tab'%pdb_id)
			os.system('rm -f %s_GenomicCoords.tab'%pdb_id)
			return 1,0
		except Exception as e:
			print "Unhandled exception chain/transcript mapping:"
			print e
			# Clean up any temporary files
			os.system('rm -f %s_PDBTranscript.tab'%pdb_id)
			os.system('rm -f %s_Alignment.tab'%pdb_id)
			os.system('rm -f %s_AlignmentScores.tab'%pdb_id)
			os.system('rm -f %s.tab'%pdb_id)
			os.system('rm -f %s_GenomicCoords.tab'%pdb_id)
			return 1,0

	# Upload to the database
	num_matches = best_candidates(pdb_id,seqadv_protected)
	print("\t%d transcript(s) found.\n"%num_matches)
	publish_data(pdb_id,args.dbhost,args.dbuser,args.dbpass,args.dbname,num_matches)
	sys.stderr.write("%s was processed successfully\n"%pdb_id)
	return 0,(num_matches > 0)

def check_species(species):
	if len(species) < 1:
		return 1
	elif args.disable_human_homologue and len([spec for spec in species if spec not in ['homo_sapien','homo_sapiens']]) > 0:
		return 1
	return 0

def read_species(line):
	"""Parses the species field from a PDB file"""
	scientific = line[32:].split(';')[0].strip().replace(' ','_')
	if scientific in species_map:
		scientific = species_map[scientific]
	return scientific.lower()

def read_experiment_type(line,c):
	"""Parses a REMARK 2** field for experiment type"""
	if line[12:27] == "EXPERIMENT TYPE":
		return line[45:].strip()
	else:
		return None

def read_best_model(line,c):
	"""Parses a REMARK 210 field for best NMR model"""
	if line[11:57] == "BEST REPRESENTATIVE CONFORMER IN THIS ENSEMBLE":
		best_nmr = line[60:].strip()
		best_nmr = best_nmr.translate(None,string.letters).strip()
		if best_nmr == '':
			best_nmr = 1
		return int(best_nmr)
	else:
		return None

def read_dbref(line,c,pdb_id):
	"""Parses a DBREF field from a PDB file"""
	global scientific_speclist
	if line[26:32].strip() == "UNP":
		chain     = line[12]
		unp_id    = line[33:41].strip()
		spec_code = line[42:54].strip().split('_')[-1].lower()
		# If the spec_code isn't specified, assume human
		# May later choose to drop the structure instead
		species   = scientific_speclist.get(spec_code,'homo_sapiens')
		pdbstart  = int(line[14:18])
		dbstart   = int(line[55:60])
		offset    = dbstart - pdbstart
		# print chain,unp_id,pdb_id,pdbstart,offset,species
		c.execute("SELECT unp,offset FROM chains WHERE chain=?",(chain,))
		res = c.fetchone()
		# This easy fix should handle peptide deletions with the same offset
		# Removed until the decision is made whether to include chains with
		# large deletions.
		if not res:# or (unp_id==res[0] and offset=res[1]):
			c.execute("INSERT INTO chains VALUES (?,?,?,?,?,?)",(chain,unp_id,pdb_id,pdbstart,offset,species))
		else:
			# The fix cannot handle insertions of a different protein
			# or deletions with different offsets
			return 1
	return 0

def read_seqres(line,c):
	"""Parses a SEQRES field from a PDB file"""
	chain = line[11]
	c.execute("SELECT * FROM chains WHERE chain=?",chain)
	if c.fetchone():
		pep_subseq = line[19:70].split()
		for aa in pep_subseq:
			c.execute("INSERT INTO seqres VALUES (?,?,?)",(chain,read_seqres.index,aa))
			read_seqres.index += 1
read_seqres.index = 0

def read_seqadv(line,c):
	"""Parses a SEQADV field from a PDB file"""
	aa = line[12:15]
	chain = line[16]
	# seqres = line[18:22].strip()
	seqres = line[43:48].strip()
	# Check the seqres not blank
	if seqres:
		seqres = int(seqres)
	# Check that seqres has no insertion code
	idcode = line[22].strip()
	conflict = line[49:70].strip()
	if seqres and not idcode:
		c.execute("INSERT INTO seqadv VALUES (?,?,?,?)",(chain,seqres,aa,conflict))

def read_atom(line,c):
	"""Parses a ATOM field from a PDB file"""
	chain = line[21]
	c.execute("SELECT * FROM chains WHERE chain=?",chain)
	if c.fetchone() or args.force:
		serialnum = int(line[6:11])
		seqres = int(line[22:26])
		idcode = line[26].strip()
		aminoacid = line[17:20]
		aminoacid_oneletter = aa_code_map[aminoacid.lower()]
		x = float(line[30:38])
		y = float(line[38:46])
		z = float(line[46:54])
		# print chain,serialnum,seqres,aminoacid,aminoacid_oneletter,x,y,z
		if not idcode:
			c.execute("INSERT INTO coords VALUES (?,?,?,?,?,?,?,?)",(chain,serialnum,seqres,aminoacid,aminoacid_oneletter,x,y,z))

def write_pdb_data(pdb_id,c,con):
	"""Averages the 3D coordinates and outputs the PDB data to tabular for MySQL upload"""
	c.execute("CREATE TABLE avgcoords AS SELECT chain,seqres,aa3,aa1,AVG(x) as x,AVG(y) as y,AVG(z) as z FROM coords GROUP BY chain,seqres")
	con.commit()
	#debug
	# c.execute("SELECT * FROM chains")
	# for row in c.fetchall():
	# 	print row
	# c.execute("SELECT * FROM coords")
	# for row in c.fetchall():
	# 	print row
	#debug
	fout = open("%s.tab"%pdb_id,'w')
	writer = csv.writer(fout,delimiter="\t")
	writer.writerow(["chain","species","unp","pdbid","seqres","aa3","aa1","x","y","z"])
	#c.execute("SELECT avgcoords.chain,chains.species,chains.unp,chains.pdb,(avgcoords.seqres+chains.offset) as seqres,aa3,aa1,x,y,z FROM chains,avgcoords WHERE avgcoords.chain=chains.chain AND avgcoords.seqres >= chains.pdbstart ORDER BY avgcoords.chain,avgcoords.seqres")
	# The offset was removed with the addition of alignment tools
	# By preserving the original PDB chain seqres values, it will be easier
	# to refer back to the PDB file if questions arise.
	c.execute("SELECT avgcoords.chain,chains.species,chains.unp,chains.pdb,avgcoords.seqres as seqres,aa3,aa1,x,y,z FROM chains,avgcoords WHERE avgcoords.chain=chains.chain AND avgcoords.seqres >= chains.pdbstart ORDER BY avgcoords.chain,avgcoords.seqres")
	writer.writerows(c.fetchall())
	fout.close()

def unp2ung(unp):
	import urllib,urllib2
	url = 'http://www.uniprot.org/mapping/'
	params = {
	'from':'ACC+ID',
	'to':'UNIGENE_ID',
	'format':'tab',
	'query': '%s'%unp
	}
	data = urllib.urlencode(params)
	request = urllib2.Request(url, data)
	contact = "mike.sivley@vanderbilt.edu"
	request.add_header('User-Agent', 'Python %s' % contact)
	response = urllib2.urlopen(request)
	page = response.read(200000)
	return page.split()[-1]

def best_candidates(pdb_id,seqadv_protected):
	with open("%s_GenomicCoords.tab"%pdb_id,'r') as fin:
		reader = csv.reader(fin,delimiter='\t')
		# {(transcript,seqres: aa1)}
		gc = {(row[0],row[2]): row[3] for row in reader}
	with open("%s_PDBTranscript.tab"%pdb_id,'r') as fin:
		pdb_t_header = fin.next()
		reader = csv.reader(fin,delimiter='\t')
		# [(transcript,chain,homologue)]
		pdb_t = [(row[2],row[1],row[3]) for row in reader]
	with open('%s.tab'%pdb_id,'r') as fin:
		reader = csv.reader(fin,delimiter='\t')
		# {(chain,seqres): aa1}
		pdb_c = {(row[0],row[4]): row[6] for row in reader}
	sanitize = []

	if len(pdb_t) < 1:
		print "\tNo candidate transcripts."
		#return 0,0
		return 0

	## ------- Experimental Simple Alignment and Scoring --------- ##

	print "\tAligning sequences..."

	# Store the best alignments
	best_alignments = {}

	# Loop through each transcript-chain match
	for transcript,chain,homologue in pdb_t:

		# Reduce dictionaries to only this match
		# seqres : aa1
		gc_sub    = {int(key[1]):gc[key]    for key in gc    if key[0]==transcript}
		pdb_c_sub = {int(key[1]):pdb_c[key] for key in pdb_c if key[0]==chain}

		# Generate sequences for chain and transcript
		chnseq_start = min(pdb_c_sub.keys())
		trnseq_start = min(gc_sub.keys())

		chain_seq = ''.join(pdb_c_sub.values())
		trans_seq = ''.join(gc_sub.values())

		# Align the two sequences and return an alignment dictionary
		# mapping chain seqres to transcript seqres and an alignment score
		alignment,score,mismatch = align_sequences(chain_seq,trans_seq,chnseq_start,trnseq_start)

		# Add if this transcript-chain match has not been evaluated
		# or this score exceeds the previous best score
		if score > best_alignments.get(chain,(0,0,''))[0]:
			best_alignments[chain] = (score,mismatch,alignment,transcript)
		# Move to next transcript-chain candidate

	score_fout = open("%s_AlignmentScores.tab"%pdb_id,'w')
	score_fout.write("pdbid\tchain\ttranscript\thomologue\tscore\tperc_nongap\tperc_match\n")
	align_fout = open("%s_Alignment.tab"%pdb_id,'w')
	align_fout.write("pdbid\tchain\tchain_seq\ttranscript\ttrans_seq\n")
	score_writer = csv.writer(score_fout,delimiter='\t')
	align_writer = csv.writer(align_fout,delimiter='\t')

	# Loop through each optimally aligned transcript-chain match
	for chain,(score,mismatch,alignment,transcript) in best_alignments.iteritems():

		# Compute the percent match (incl. permissable mismatches)
		chain_len      = len(alignment)
		num_gaps       = len([val for val in alignment.values() if val==-1])
		perc_nongap    = float(chain_len-num_gaps) / chain_len
		perc_match     = float(chain_len-num_gaps-mismatch) / chain_len

		# Write the full alignment summary
		score_writer.writerow([pdb_id,chain,transcript,homologue,"%2.2f"%score,"%2.2f"%perc_nongap,"%2.2f"%perc_match])

		# Write the individual alignment pairs
		for chain_seq,trans_seq in alignment.iteritems():
			align_writer.writerow([pdb_id,chain,chain_seq,transcript,trans_seq])

	score_fout.close()
	align_fout.close()
	aligned_transcripts = len(best_alignments)
	return aligned_transcripts

	## ----------------------------------------------------------- ##

	#	Deprecated chain-transcript mapping code 
	#
	# # For each mapping
	# pdb_t_conflict = []
	# for transcript,chain,homologue in pdb_t:

	# 	# Track the number of conflicts
	# 	num_conflicts = 0

	# 	# Reduce by first key and remove
	# 	gc_sub    = {int(key[1]):gc[key]    for key in gc    if key[0]==transcript}
	# 	pdb_c_sub = {int(key[1]):pdb_c[key] for key in pdb_c if key[0]==chain}
	# 	# Join by second key and compare values
	# 	for seqres in pdb_c_sub:
	# 		# If a protected SEQADV conflict, skip
	# 		if (chain,seqres) in seqadv_protected:
	# 			pass
	# 		# If the transcript does not contain the seqres, discard
	# 		elif seqres not in gc_sub:
	# 			num_conflicts += 1
	# 		# Or the amino acid is different at that seqres, discard
	# 		elif gc_sub[seqres] != pdb_c_sub[seqres]:
	# 			num_conflicts += 1

	# 	# Determine % conflict
	# 	if len(pdb_c_sub) > 0:
	# 		perc_conflict = num_conflicts / float(len(pdb_c_sub))
	# 	else:
	# 		perc_conflict = 1.0

	# 	# Retain if conflict < 90%
	# 	# if perc_conflict < 0.90:
	# 	pdb_t_conflict.append((transcript,chain,homologue,perc_conflict))

	# # if len(pdb_t_conflict) < 1:
	# # 	print "\tAll transcripts failed QC. <10% match."
	# # 	return 0

	# # Sort by chain and display
	# pdb_t_conflict.sort(key=lambda x: x[1])
	# # print "\tAll candidates:"
	# # for chain,transcript,homologue,perc_conflict in pdb_t_conflict:
	# # 	print "\t\t%s.%s -> %s: %2.2f conflict"%(pdb_id,chain,transcript,perc_conflict)

	# # Determine the best transcript match for each chain. Arbitrary tie breaking
	# best_candidates = []
	# for chain in set([chain for x,chain,y,z in pdb_t_conflict]):
	# 	conflicts = [candidate[3] for candidate in pdb_t_conflict if candidate[1]==chain]
	# 	min_conflict = min(conflicts)
	# 	best_candidate = [tup for tup in pdb_t_conflict if tup[1]==chain and tup[3]==min_conflict][0]
	# 	best_candidates.append(best_candidate)

	# best_candidates.sort(key=lambda x: x[1])
	# # print "\n\tBest candidates:"
	# # for chain,transcript,homologue,perc_conflict in best_candidates:
	# # 	print "\t\t%s.%s -> %s: %2.2f conflict"%(pdb_id,chain,transcript,perc_conflict)
	# # And write the sanitized mappings back to file
	# if len(pdb_t_conflict):
	# 	with open('PDBTranscript.tab','w') as fout:
	# 		writer = csv.writer(fout,delimiter='\t')
	# 		# for transcript,chain,homologue in pdb_t:
	# 		for transcript,chain,homologue,conflict in best_candidates:
	# 			writer.writerow([pdb_id,chain,transcript,homologue,"%2.2f"%conflict])

	# Return the number of remaining matches
	#return len(best_candidates),aligned_transcripts

def align_sequences(seq1,seq2,seq1_start=1,seq2_start=1):
	""" Experimental inclusion to align sequences """
	# Default start values ensure 1-indexed results post-gap shift
	matrix     = matlist.blosum62
	gap_open   = -10
	gap_extend = -0.5

	alignments = pairwise2.align.globalds(seq1,seq2,matrix,gap_open,gap_extend)
	best_align = alignments[0]
	aln_seq1_str, aln_seq2_str, score, begin, end = best_align
	aln_seq1   = [aa for aa in aln_seq1_str]
	aln_seq2   = [aa for aa in aln_seq2_str]

	# Alignment dictionary directed: seq1->seq2
	seq1_ind = [x for x in gap_shift(aln_seq1,seq1_start)]
	seq2_ind = [x for x in gap_shift(aln_seq2,seq2_start)]
	mismatch = sum([int(aln_seq1[i]!=aln_seq2[i]) for i in range(len(aln_seq1)) if seq1_ind[i] > 0 and seq2_ind[i] > 0])
	aln_dict = dict((seq1_ind[i],seq2_ind[i]) for i in range(len(seq1_ind)) if seq1_ind[i] > 0)
	return aln_dict,score,mismatch
	
def gap_shift(seq,seq_start):
	""" Experimental inclusion to align sequences """
	# Returns a dictionary mapping
	index = seq_start
	for i in seq:
		if i != '-':
			yield index
			index += 1
		else:
			yield -1

def publish_data(pdb_id,dbhost,dbuser,dbpass,dbname,num_matches):
	try:
		con = MySQLdb.connect(host=dbhost,user=dbuser,passwd=dbpass,db=dbname)
		c = con.cursor()
	except MySQLdb.Error as e:
		print "There was an error connecting to the database.\n%s"%e
		sys.exit(1)
	try:
		query = ["LOAD DATA LOCAL INFILE '%s.tab' INTO TABLE PDBInfo FIELDS TERMINATED BY '\t' LINES TERMINATED BY '\n' IGNORE 1 LINES (chain,species,unp,pdbid,@dummy,@dummy,@dummy,@dummy,@dummy,@dummy)"%pdb_id]
		# Only load the rest if there were any successful matches
		if num_matches > 0:
			query.append("LOAD DATA LOCAL INFILE '%s_GenomicCoords.tab' INTO TABLE GenomicCoords FIELDS TERMINATED BY '\t' LINES TERMINATED BY '\n' IGNORE 1 LINES"%pdb_id)
			# query.append("LOAD DATA LOCAL INFILE 'PDBTranscript.tab' INTO TABLE PDBTranscript FIELDS TERMINATED BY '\t' LINES TERMINATED BY '\n'")
			query.append("LOAD DATA LOCAL INFILE '%s_AlignmentScores.tab' INTO TABLE AlignmentScores FIELDS TERMINATED BY '\t' LINES TERMINATED BY '\n' IGNORE 1 LINES"%pdb_id)
			query.append("LOAD DATA LOCAL INFILE '%s_Alignment.tab' INTO TABLE Alignment FIELDS TERMINATED BY '\t' LINES TERMINATED BY '\n' IGNORE 1 LINES"%pdb_id)
			query.append("LOAD DATA LOCAL INFILE '%s.tab' INTO TABLE PDBCoords FIELDS TERMINATED BY '\t' LINES TERMINATED BY '\n' IGNORE 1 LINES (chain,@dummy,@dummy,pdbid,seqres,aa3,aa1,x,y,z)"%pdb_id)
			# query.append("CALL %s.update_GenomePDB('%s');"%(dbname,pdb_id))
		end_of_query = ['.','...']
		print("\tUploading staging files to database...")
		for q in query:
			tq0  = time.time()
			sys.stdout.write("\t\t%s%s - "%(q[:35],end_of_query[int(len(q)>35)]))
			sys.stdout.flush()
			c.execute(q)
			tqel = time.time()-tq0
			sys.stdout.write("%2.2fs\n"%tqel)
			sys.stdout.flush()
	except (KeyboardInterrupt,SystemExit):
		print("\tSkipping:")
		sys.stdout.write("\tUpload to MySQL was interrupted by user.")
		raise KeyboardInterrupt
	except Exception as e:
		print("\tSkipping:")
		sys.stdout.write("\tUpload to MySQL failed: %s."%e)
	finally:
		con.close()	# Close the remote MySQL connection
		os.system('rm -f %s_PDBTranscript.tab'%pdb_id)
		os.system('rm -f %s_AlignmentScores.tab'%pdb_id)
		os.system('rm -f %s_Alignment.tab'%pdb_id)
		os.system('rm -f %s.tab'%pdb_id)
		os.system('rm -f %s_GenomicCoords.tab'%pdb_id)

def get_new_pdbs(pdbs,dbhost,dbuser,dbpass,dbname):
	try:
		con = MySQLdb.connect(host=dbhost,user=dbuser,passwd=dbpass,db=dbname)
		c = con.cursor()
	except MySQLdb.Error as e:
		print "There was an error connecting to the database.\n%s"%e
		sys.exit(1)
	c.execute("SELECT DISTINCT(pdbid) FROM PDBInfo")
	res = [tup[0] for tup in c.fetchall()]
	new_pdbs = [(pdb_id,pdb_file) for pdb_id,pdb_file in pdbs.iteritems() if pdb_id not in res]
	con.close()
	return new_pdbs

def create_new_db(dbhost,dbuser,dbpass,dbname):
	try:
		con = MySQLdb.connect(host=dbhost,user=dbuser,passwd=dbpass)
		c = con.cursor()
	except MySQLdb.Error as e:
		print "There was an error connecting to the database.\n%s"%e
		sys.exit(1)
	query = ["DROP DATABASE IF EXISTS %s"%dbname]
	query.append("CREATE DATABASE IF NOT EXISTS %s"%dbname)
	query.append("USE %s"%dbname)
	query.append("CREATE TABLE %s.GenomicCoords (transcript VARCHAR(50),gene VARCHAR(50), seqres INT,aa1 VARCHAR(1),start BIGINT,end BIGINT,chr VARCHAR(20),strand INT,PRIMARY KEY(transcript,seqres),KEY(transcript),KEY(start,end,chr))"%dbname)
	query.append("CREATE TABLE %s.PDBCoords (pdbid VARCHAR(50),chain VARCHAR(1),seqres INT,aa3 VARCHAR(3),aa1 VARCHAR(1),x DOUBLE,y DOUBLE,z DOUBLE,PRIMARY KEY(pdbid,chain,seqres))"%dbname)
	query.append("CREATE TABLE %s.PDBInfo (pdbid VARCHAR(50),species VARCHAR(50),chain VARCHAR(10),unp VARCHAR(50),PRIMARY KEY(pdbid,chain))"%dbname)
	# query.append("CREATE TABLE %s.PDBTranscript (pdbid VARCHAR(20),chain VARCHAR(1),transcript VARCHAR(20),homologue BOOLEAN,conflict REAL,PRIMARY KEY(pdbid,chain,transcript),KEY(transcript),KEY(conflict))"%dbname)
	query.append("CREATE TABLE %s.AlignmentScores (pdbid VARCHAR(50),chain VARCHAR(10),transcript VARCHAR(50),homologue BOOLEAN,score REAL,perc_nongap REAL,perc_match REAL,PRIMARY KEY(pdbid,chain,transcript),KEY(transcript),KEY(pdbid,chain),KEY(score),KEY(perc_nongap),KEY(perc_match))"%dbname)
	query.append("CREATE TABLE %s.Alignment (pdbid VARCHAR(50),chain VARCHAR(10),chain_seq INT,transcript VARCHAR(50),trans_seq INT,PRIMARY KEY(pdbid,chain,chain_seq,transcript,trans_seq),KEY(transcript),KEY(pdbid),KEY(pdbid,chain))"%dbname)
	# query.append("""CREATE TABLE `%s`.`GenomePDB` (
 #  		`pdbid` VARCHAR(50) NOT NULL default '',
 #  		`species` VARCHAR(50) default NULL,
 #  		`chain` VARCHAR(10) NOT NULL default '',
 #  		`unp` VARCHAR(20) default NULL,
 #  		`gene` VARCHAR(20) default NULL,
 #  		`transcript` VARCHAR(20) default NULL,
 #  		`seqres` INT(11) NOT NULL default '0',
 #  		`aa1` VARCHAR(1) default NULL,
 #  		`x` DOUBLE default NULL,
 #  		`y` DOUBLE default NULL,
 #  		`z` DOUBLE default NULL,
 #  		`start` BIGINT(20) default NULL,
 #  		`end` BIGINT(20) default NULL,
 #  		`chr` VARCHAR(20) default NULL,
 #  		`strand` INT(11) default NULL,
 #  		PRIMARY KEY `transpos` (`pdbid`,`chain`,`transcript`,`chr`,`start`,`end`,`strand`),
 #  		KEY `gene` (`gene`),
 #  		KEY `peptide` (`pdbid`,`chain`,`seqres`),
 #  		KEY `genomic` (`chr`,`start`,`end`),
 #  		KEY `pdbid` (`pdbid`)
	# 	)"""%dbname)
	format_dict = {'dbuser':dbuser,'dbhost':dbhost}
	with open('create_proc_update_GenomePDB.sql','r') as fin:
		query.append(fin.read()%format_dict)
	with open('create_proc_build_GenomePDB.sql','r') as fin:
		query.append(fin.read()%format_dict)
	for q in query:
		c.execute(q)
	con.close()

aa_code_map = {"ala" : "A",
				"arg" : "R",
				"asn" : "N",
				"asp" : "D",
				"asx" : "B",
				"cys" : "C",
				"glu" : "E",
				"gln" : "Q",
				"glx" : "Z",
				"gly" : "G",
				"his" : "H",
				"ile" : "I",
				"leu" : "L",
				"lys" : "K",
				"met" : "M",
				"phe" : "F",
				"pro" : "P",
				"ser" : "S",
				"thr" : "T",
				"trp" : "W",
				"tyr" : "Y",
				"val" : "V"}

species_map = {"PIG" : "sus_scrofa",
				"BAKER'S YEAST" : "saccharomyces_cerevisiae",
				"YEAST" : "saccharomyces_cerevisiae"}

def load_speclist(speclist_file):
	fin = open(speclist_file,'r')
	scientific_speclist = {}
	common_speclist = {}
	spec_code = ''
	for line in fin:
		if line[0:5]:
			spec_code = line[0:5].lower()
		if line.strip() and line[17].upper() == 'N':
			scientific_speclist[spec_code] = line[19:].strip().lower().replace(' ','_')
		elif line.strip() and line[17].upper() == 'C':
			common_speclist[spec_code] = line[19:].strip().upper()
	fin.close()
	return scientific_speclist,common_speclist

def load_transmap(transmap_file):
	with open(transmap_file) as fin:
		reader = csv.reader(fin,delimiter='\t')
		transmap = {}
		for (unp,id_type,trans) in reader:
			if unp in transmap:
				transmap[unp].append((trans,id_type))
			else:
				transmap[unp] = [(trans,id_type)]
	return transmap

# Initialized below
scientific_speclist = {}
common_speclist     = {}
transmap            = {}

if __name__=='__main__':
	args = parser.parse_args(remaining_argv)
	args.create_new_db = bool(args.create_new_db)
	args.disable_human_homologue = bool(args.disable_human_homologue)
	args.force = bool(args.force)
	if args.create_new_db and not args.force:
		print "You have opted to create a new database."
		print "This will overwrite any existing database by the same name."
		if raw_input("Are you sure you want to do this? (y/n):") == 'n':
			print "Aborting..."
			sys.exit(0)

	# Load the species code -> species map
	scientific_speclist,common_speclist = load_speclist(args.speclist)

	# Load the UNP -> transcript map
	transmap = load_transmap(args.transmap)

	# Begin processing
	main()
