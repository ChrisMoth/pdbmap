-- --------------------------------------------------------------------------------
-- Routine DDL
-- Note: comments before and after the routine body will not be stored by the server
-- --------------------------------------------------------------------------------
DELIMITER $$

CREATE DEFINER=`sivleyrm`@`10.%.%.%` PROCEDURE `assign_foreign_keys`(slabel VARCHAR(100), dlabel VARCHAR(100))
BEGIN
# Chain -> Structure
UPDATE Chain a INNER JOIN Structure b ON a.label=b.label AND a.structid=b.pdbid
SET a.str_id=b.str_id WHERE a.label=slabel;
# Chain -> Model
UPDATE Chain a INNER JOIN Model b ON a.label=b.label AND a.structid=b.modelid
SET a.str_id=b.str_id WHERE a.label=slabel;
# Residue -> Chain
UPDATE Residue a INNER JOIN Chain b ON a.label=b.label AND a.structid=b.structid AND a.chain=b.chain
SET a.ch_id=b.ch_id WHERE a.label=slabel;
# Alignment -> Residue
UPDATE Alignment a INNER JOIN Residue b ON a.label=b.label AND a.structid=b.structid AND a.chain=b.chain AND a.chain_seqid=b.seqid
SET a.res_id=b.res_id WHERE a.label=slabel;
# Alignment -> AlignmentScore
UPDATE Alignment a INNER JOIN AlignmentScore b ON a.label=b.label AND a.structid=b.structid AND a.chain=b.chain AND a.transcript=b.transcript
SET a.as_id=b.as_id WHERE a.label=slabel;
# Alignment -> Transcript
UPDATE Alignment a INNER JOIN Transcript b ON a.label=b.label AND a.transcript=b.transcript AND a.trans_seqid=b.seqid
SET a.tr_id=b.tr_id WHERE a.label=slabel;
# Transcript -> GenomicConsequence
UPDATE Transcript a INNER JOIN GenomicConsequence b ON a.label=b.label AND a.transcript=b.transcript AND a.chr=b.chr AND b.start >= a.start AND b.end <= a.end
SET a.gc_id=b.gc_id WHERE a.label=slabel;
# GenomicConsequence -> GenomicData
UPDATE GenomicConsequence a INNER JOIN GenomicData b ON a.label=b.label AND a.chr=b.chr AND a.start=b.start AND a.end=b.end AND a.name=b.name
SET a.gd_id=b.gd_id WHERE a.label=dlabel;
# GenomicIntersection -> GenomicConsequence (ASSIGNED DURING INTERSECTION)
# UPDATE GenomicIntersection a INNER JOIN GenomicConsequence b SET a.gc_id=b.gc_id WHERE label=label;
# GenomicIntersection -> Residue
UPDATE GenomicIntersection a INNER JOIN Residue b ON a.slabel=b.label AND a.structid=b.structid AND a.chain=b.chain AND a.seqid=b.seqid
SET a.res_id=b.res_id WHERE a.dlabel=dlabel and a.slabel=slabel;
END