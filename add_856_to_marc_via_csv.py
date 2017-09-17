# -*- coding: utf-8 -*-
"""

Created on Tue Dec  6 09:50:50 2016
jeff gerhard / gerhardj@gmail.com

Python 3 program to add links to MARC records based on matching bib record values

1.  Takes a MARC file exported from III's Sierra (i.e., the "out" file regard-
    less of extension);

2.  Uses MARCEdit command-line tool to break to mnemonic MARK (mrk) format;

3.  Goes through the file line by line, copying each line to a new record
    with the following edits:
        A. Fix 001 OCLC number;
        B. Copy cat date and bib number from the 907 field into variables;
        C. Add a 949 overlay field with the cat date and bib number;
        D. Delete miscellaneous 9xx data fields that do not input back into
           Sierra regardless

4.  Build 856 links based on a required csv file formatted with
    bib number, identifier, and volume. Note that bib numbers can repeat on
    this list if a single bib record is related to more than one identifier,
    as is the case for multivolume sets

    Sample csv lines:

        BibID,identifier,volume
        b1480649,aaasprofessi_chal_1980_000_6647977,
        b2355103,aborig_swa_1991_00_6265,
        b4137449,academicinst_garb_2001_000_7677585,
        b4088633,collectedess_fox_2003_001_7609521,1
        b4088633,collectedess_fox_2003_002_7526030,2

    Basically, for each bib record in the marc file, we will search against this
    csv and add 856 links with the identifiers indicated for any matches found.

5.  Create a temp file with the new records, then compile that into a .mrc
    MARC file by again calling the MARCEdit command-line tool

This SHOULD create a record ready to load into Sierra's Data Exchange module.

For now this is designed to run on Windows with files residing in a single
directory -- the csv, this python script, and the output MARC file.

There is a variable cmarcedit with a path to the MARCEdit commandline tool
cmarcedit.exe. Adjust as needed.

More on the MARCEdit and cmarcedit at
http://marcedit.reeset.net/cmarcedit-exe-using-the-command-line

How-to on running command line tools from python at
http://stackoverflow.com/questions/14894993/running-windows-shell-commands-with-python

"""

import csv
from subprocess import check_call
import os
from tkinter.filedialog import askopenfilename


def oclc001(line):
    # see http://www.oclc.org/en-US/batchload/controlnumber.html
    # III exports do not include required prefixes but do need to have them
    # when overlaying
    no = line[6:]
    if len(no) < 9:
        no = 'ocm' + no.zfill(8)
    elif len(no) == 9:
        no = 'ocn' + no
    elif len(no) > 9:
        no = 'on' + no
    return '=001  ' + no


def data907(line):
    # take the info needed for the 856 and the 949 but delete the actual 907
    bibno = 'b' + (line.split('.b')[1]).split('$')[0]
    catdate = (line.split('$c')[1]).split('$')[0]
    return bibno, catdate


def add856(bibno, bibmatches):
    # check against the csv for all matches and potentially volume info
    results = list()
    for b in bibmatches:
        if b['BibID'] == bibno:
            fieldstring = '=856  40$xInternet Archive$zDigitized copy'
            if b['volume'] != '':
                fieldstring += ' of v. ' + b['volume']
            fieldstring += ' available for e-checkout$uhttp://archive.org/details/'
            fieldstring += b['identifier']
            results.append(fieldstring)
    return results


def add949(bibno, catdate):
    return r'=949  \\$a*recs=b;ov=.{};ct={};'.format(bibno, catdate)


# DEFINE VARIABLES AND ASK FOR MRC FILE
cmarcedit = r'C:\Program Files\MarcEdit 6\cmarcedit.exe'
fname = askopenfilename(title='Choose a .mrc file')
step = fname[:-4] + '.mrk'
temp = fname[:-4] + '_temp.mrk'

# RUN MARCEDIT TO BREAK MRC
print('\nBreaking MARC record...')
check_call('{} -s {} -d {} -break'.format(cmarcedit, fname, step))

# LOAD CSV INTO MEMORY AS DICTIONARY
bibmatches = list()
with open('match.csv', 'r', encoding='utf-8') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        bibmatches.append(row)

# READ THE MRK FILE AS TEXT
with open(step, 'r', encoding='utf-8') as fh:
    content = fh.read()

lines = content.splitlines()
newrecord = list()
deletedfields = list()
existing_stats = list()
extra = False
totalbibs = 0
totallinks = 0
# BUILD NEW RECORD LINE BY LINE
for line in lines:
    if line[1:4] == '001':
        newrecord.append(oclc001(line))
    elif line[1:4] == '856':
        existing_stats.append(line)
        extra = True
    elif line[1:4] == '907':
        bibno, catdate = data907(line)
        links = add856(bibno, bibmatches)
        for link in links:
            newrecord.append(link)
        deletedfields.append(line)
        if extra:
            existing_stats.append(bibno)
            extra = False
    elif line[1:4] in ['999', '907', '949', '998', '971']:
        deletedfields.append(line)
    elif line == '':
        newrecord.append(add949(bibno, catdate))
        newrecord.append(line)
        summary = ''
        if links:
            summary = '- added ' + str(len(links)) + ' link'
            if len(links) > 1:
                summary += 's'
            print('processed', bibno, summary)
            totalbibs += 1
            totallinks += len(links)
    else:
        newrecord.append(line)

# WRITE TEMP MRK RECORD
with open(temp, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(newrecord))

# COMPILE TO MARC VIA MARCEDIT
print('\nCompiling MARC record...')
check_call('{} -s {} -d {}_output.mrc -make'.format(cmarcedit, temp, fname[:-4]))
# can probs delete the interim files
os.remove(temp)
os.remove(step)

print('deleted {} lines of extraneous 9xx fields -- check log for details'.format(len(deletedfields)))
with open('deleted_fields.log', 'w') as fh:
    fh.write('\n'.join(deletedfields))

with open('existing_856.log', 'w') as fh:
    fh.write('\n'.join(existing_stats))

print('Added {} links; modified {} bib records.'.format(totallinks, totalbibs))
