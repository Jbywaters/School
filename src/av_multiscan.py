#!/usr/bin/env python
# encoding: utf-8
#
# This program is intended to run on a Linux machine, but you could
# easily use it on Windows (remove the Wine stuff and run exe's directly)
#
"""
av_multi_scanner.py

Created by Matthew Richard on 2010-01-1.
Copyright (c) 2010. All rights reserved.
"""

import sys
import os
import yara
from hashlib import md5
import subprocess
import socket
from time import localtime, strftime
import re
from optparse import OptionParser

# configuration information to use when processing the 
# various AV products
# please update to reflect the paths on your system
yara_conf_file = "magic.yara"
clam_conf_file = "clam_shellcode.ndb"
yara_packer_file = "packer.yara"
path_to_ssdeep = os.getcwd()+'\ssdeep.exe'
path_to_clamscan = "/usr/local/bin/clamscan"
path_to_fpscan = "/usr/local/bin/fpscan"
path_to_officemalscanner = "/data/tools/OfficeMalScanner/OfficeMalScanner.exe"
ssdeep_params = ''


# add new functions by invoking the scanner
# and returning a dictionary that contains
# the keys 'name' and 'result'
# where 'name' is the name of the scanner
# and 'result' contains a string representing the results

def md5sum(data):
    m = md5()
    m.update(data)
    return ({'name': 'md5', 'result': m.hexdigest()})


def ssdeep(fname):
    print path_to_ssdeep
    if os.path.isfile(path_to_ssdeep):
        output = subprocess.Popen([path_to_ssdeep, ssdeep_params, fname], stdout=subprocess.PIPE).communicate()[0]
        response = output.split()[1].split(',')[0]
    else:
        response = 'ERROR - SSDEEP NOT FOUND'
    return (response)


def yarascan(data2):
    if os.path.isfile(yara_conf_file):
        rules = yara.compile(yara_conf_file)
        result = rules.match(data=data2)
        out = ''
        for m in result:
            out += "'%s' " % m
        response = out
    else:
        response = "ERROR - YARA Config Missing"
    return ({'name': 'yara', 'result': response})


def yara_packer(data2):
    if os.path.isfile(yara_packer_file):
        rules = yara.compile(yara_packer_file)
        result = rules.match(data=data2)
        out = ''
        for m in result:
            out += "'%s' " % m
        response = out
    else:
        response = "ERROR - YARA Config Missing"
    return ({'name': 'yara_packer', 'result': response})


def clam_custom(fname):
    # check to see if the right path for the scanner and
    # the custom configuration file exist
    if os.path.isfile(path_to_clamscan) and os.path.isfile(clam_conf_file):
        output = \
        subprocess.Popen([path_to_clamscan, "-d", clam_conf_file, fname], stdout=subprocess.PIPE).communicate()[0]
        result = output.split('\n')[0].split(': ')[1]
    else:
        result = 'ERROR - %s not found' % path_to_clamscan
    return ({'name': 'clam_custom', 'result': result})


def clamscan(fname):
    if os.path.isfile(path_to_clamscan):
        output = subprocess.Popen([path_to_clamscan, fname], stdout=subprocess.PIPE).communicate()[0]
        result = output.split('\n')[0].split(': ')[1]
    else:
        result = 'ERROR - %s not found' % path_to_clamscan
    return ({'name': 'clamav', 'result': result})


def fpscan(fname):
    """ Depending on the version of FPROT you use, you may need
    to adjust the RESULTLINE number. """
    RESULTLINE = 10
    if os.path.isfile(path_to_fpscan):
        output = \
        subprocess.Popen([path_to_fpscan, "--report", fname], stdout=subprocess.PIPE, stderr=None).communicate()[0]
        result = output.split('\n')[RESULTLINE].split('\t')[0]
    else:
        result = 'ERROR - %s not found' % path_to_fpscan
    return ({'name': 'f-prot', 'result': result})


def officemalscanner(fname):
    if os.path.isfile(path_to_officemalscanner):
        env = os.environ.copy()
        env['WINEDEBUG'] = '-all'
        output = subprocess.Popen(["wine", path_to_officemalscanner,
                                   fname, "scan", "brute"], stdout=subprocess.PIPE, stderr=None, env=env).communicate()[
            0]
        if "Analysis finished" in output:
            output = output.split('\r\n')
            while "Analysis finished" not in output[0]:
                output = output[1:]
            result = output[3]
        else:
            result = "Not an MS Office file"
    else:
        result = 'ERROR - %s not found' % path_to_officemalscanner
    return ({'name': 'officemalscanner', 'result': result})


def cymruscan(data):
    # this scanner works by sending a request to hash.cymru.com
    # over port 43 and sending a list of md5's to check
    # if the md5 exists in the database they return the
    # number of av vendors detecting the file and the
    # date the file was last seen
    md5 = md5sum(data)
    md5 = md5['result']
    request = '%s\r\n' % md5
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect(('hash.cymru.com', 43))
        s.send('begin\r\n')
        s.recv(1024)
        s.send(request)
        response = s.recv(1024)
        s.send('end\r\n')
        s.close()
        if len(response) > 0:
            resp_re = re.compile('\S+ (\d+) (\S+)')
            match = resp_re.match(response)
            response = "%s - %s" % (strftime("%a, %d %b %Y %H:%M:%S", localtime(int(match.group(1)))), match.group(2))
    except socket.error:
        response = "ERROR - NOT AVAILABLE"
    return ({'name': 'cymru_hash_db', 'result': response})


def filesize(data):
    return ({'name': 'filesize', 'result': str(len(data))})


def filename(filename):
    return ({'name': 'filename', 'result': filename})


def main():
    parser = OptionParser()
    parser.add_option("-f", "--file", action="store", dest="filename",
                      type="string", help="scanned FILENAME")
    parser.add_option("-v", "--verbose", action="store_true", default=False,
                      dest="verbose", help="verbose")

    (opts, args) = parser.parse_args()

    if opts.filename == None:
        parser.print_help()
        parser.error("You must supply a filename!")
    if not os.path.isfile(opts.filename):
        parser.error("%s does not exist" % opts.filename)

    data = open(opts.filename, 'rb').read()
    results = []
    results.append(filename(opts.filename))
    results.append(filesize(data))
    results.append(md5sum(data))
    results.append(ssdeep(opts.filename))
    results.append(clamscan(opts.filename))
    results.append(clam_custom(opts.filename))
    results.append(yarascan(data))
    results.append(yara_packer(data))
    results.append(officemalscanner(opts.filename))
    results.append(fpscan(opts.filename))
    results.append(cymruscan(data))

    if opts.verbose:
        print "[+] Using YARA signatures %s" % yara_conf_file
        print "[+] Using ClamAV signatures %s" % clam_conf_file
        print "\r\n"
    for result in results:
        if ("ERROR" in result['result']) and (opts.verbose == False):
            continue
        print "%20s\t%-s" % (result['name'], result['result'])
    print "\r\n"


if __name__ == '__main__':
    main()