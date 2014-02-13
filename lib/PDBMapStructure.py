#!/usr/bin/env python27
#
# Project        : PDBMap
# Filename       : PDBMapStructure.py
# Author         : R. Michael Sivley
# Organization   : Center for Human Genetics Research,
#                : Department of Biomedical Informatics,
#                : Vanderbilt University Medical Center
# Email          : mike.sivley@vanderbilt.edu
# Date           : 2014-02-12
# Description    : Wrapper for Bio.PDB.Structure.Structure with additional
#                : information and functionality pertinent to PDBMap. All
#                : requests for Structure attributes are deferred to the
#                : Structure object.
#=============================================================================#

# See main check for cmd line parsing
import sys,os,csv
from Bio.PDB.Structure import Structure
from lib.PDBMapTranscript import PDBMapTranscript

class PDBMapStructure(Structure):

  def __init__(self,s,tier=-1,quality=-1):
    # Assign the Structure, tier, and quality
    self.structure   = s
    self.tier        = tier
    self.quality     = quality
    self.transcripts = []

  def __getattr__(self,attr):
    # Defer appropriate calls to the structure
    if attr in dir(self.structure):
      result = self.structure.__getattribute__(attr)
    else:
      result = self.__getattribute__(attr)
    if callable(result):
      def hooked(*args, **kwargs):
        result = result(*args,**kwargs)
        if result == self.structure:
          return self
        return result
      return hooked
    else:
      return result

  def get_transcripts(self):
    # Retrieve the corresponding transcript for each chain
    if self.transcripts:
      return self.transcripts
    for chain in self.structure[0]:
      candidate_transcripts = PDBMapTranscript(unpid=chain.unp)
      # Align candidate transcripts to chain
      alignment = PDBMapAlignment(chain,candidate_transcripts[0])
      for trans in candidate_transcripts[1:]:
        new_alignment = PDBMapAlignment(chain,trans)
        # Determine best alignment
        if new_alignment.score > alignment.score:
          alignment = new_alignment
        # Store best transcript alignment as element of chain
       chain.alignment  = alignment
       chain.transcript = alignment.transcript
    # Return the matched transcripts
    return [chain.transcript for chain in self.structure[0]]

# Main check
if __name__== "__main__":
  sys.stderr.write("Class definition. Should not be called from command line.")
  sys.exit(1)

# This class was a pain in the ass to write. Thank you to:
# http://stackoverflow.com/questions/1466676/create-a-wrapper-class-
# to-call-a-pre-and-post-function-around-existing-functions
