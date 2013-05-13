#!/usr/bin/python

# Improvements:
#
# 1. Update so that it loops through all PDBIDs in the scores file
# 2. Dynamically fetch PDB structures in the loop
# 3. Document the required format for the scores file
# 4. Automatically center on high/low scored regions and generate png

import sys,csv
if __name__ != "__main__":
	from pymol import cmd
else:
	cmd = None

def overwrite_bfactor(pdbid,chain,resi,value):
	selection = "(%s and chain %s and resi %d)"%(pdbid,chain,resi)
	exp = "b=%f"%value
	command = "Altering %s"%selection
	command += "; Expression: %s"%exp
	if __name__ != "__main__":
		cmd.alter(selection,exp)
	return command

def reset_bfactor(pdbid):
	exp = "b=0.0"
	cmd.alter(pdbid,exp)

def overwrite_bfactors(pdbid,score_file,resis=None):
	fin = open(score_file,'r')
	reader = csv.reader(fin,delimiter='\t')
	if resis:
		scores = [row for row in reader if row[0]==pdbid and int(row[2]) in resis]
	else:
		scores = [row for row in reader if row[0]==pdbid]
	fin.close()
	min_score = min([float(score[3]) for score in scores if float(score[3]) > -8])
	max_score = max([float(score[3]) for score in scores])

	if __name__ != "__main__":
		reset_bfactor(pdbid)
	commands = [overwrite_bfactor(row[0],row[1],int(row[2]),float(row[3])) for row in scores]
	include = "br. b > %f"%min_score
	exclude = "br. b < %f"%min_score
	print("Minimum score: %s"%min_score)
	print("Maximum score: %s"%max_score)
	cmd.spectrum("b","blue_red",selection=include,minimum=min_score,maximum=max_score)
	cmd.color("grey",exclude)
	cmd.hide("everything","all")
	cmd.show(representation="sticks")
	# Optional
	#cmd.show("spheres","br. b<0.9")
	return commands


if __name__=="__main__":
	commands = overwrite_bfactors(sys.argv[1],sys.argv[2])
	print "Commands:"
	for command in commands:
		print command
else:
	cmd.extend("overwrite_bfactors",overwrite_bfactors)