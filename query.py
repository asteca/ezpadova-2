"""
This script is based on:

EZPADOVA -- A python package that allows you to download PADOVA isochrones
directly from their website

https://github.com/mfouesneau/ezpadova
"""


import sys
import requests
from bs4 import BeautifulSoup
import zlib
import re
import numpy as np
from os.path import join, exists
import configparser
from pathlib import Path
from os import makedirs

webserver = 'http://stev.oapd.inaf.it'

# Available sets of tracks (PARSEC + COLIBRI).
map_models = {
    'PAR12+CS_37': ('parsec_CAF09_v1.2S', 'parsec_CAF09_v1.2S_S_LMC_08_web',
                    'PARSEC v1.2S + COLIBRI S_37'),
    'PAR12+CS_35': ('parsec_CAF09_v1.2S', 'parsec_CAF09_v1.2S_S35',
                    'PARSEC v1.2S + COLIBRI S_35'),
    'PAR12+CS_07': ('parsec_CAF09_v1.2S', 'parsec_CAF09_v1.2S_S07',
                    'PARSEC v1.2S + COLIBRI S_07'),
    'PAR12+CPR16': ('parsec_CAF09_v1.2S', 'parsec_CAF09_v1.2S_NOV13',
                    'PARSEC v1.2S + COLIBRI PR16'),
    'PAR12+No': ('parsec_CAF09_v1.2S', 'no', 'PARSEC v1.2S + No')
}

# To create this dictionary:
# 1. Download the CMD input form as an HTML file
# 2. Use this regex query in the HTML file to find all the inputs:
#    input type.*?value.*?>
# 3. Extract the clean lines with a 'checked' in them
# 4. Add the 'imf_file' line that is not selected with the regex search
__def_args__ = {
    "submit_form": (None, "Submit"),
    "track_parsec": (None, "parsec_CAF09_v1.2S"),
    "track_colibri": (None, "no"),
    "track_postagb": (None, "no"),
    "photsys_version": (None, "YBCnewVega"),
    "dust_sourceM": (None, "dpmod60alox40"),
    "dust_sourceC": (None, "AMCSIC15"),
    "extinction_coeff": (None, "constant"),
    "extinction_curve": (None, "cardelli"),
    "kind_LPV": (None, "1"),
    "isoc_isagelog": (None, "1"),
    "isoc_ismetlog": (None, "0"),
    "output_kind": (None, "0"),
    'imf_file': (None, "tab_imf/imf_kroupa_orig.dat")
}
# This root is important, it will change from time to time
phot_syst_file = 'YBC_tab_mag_odfnew/tab_mag'


def main():

    # Read input parameters from file.
    gz_flag, evol_track, rm_label9, phot_syst, phot_syst_v, z_range, a_range =\
        readINI()

    # Read optional argument
    try:
        _arg = sys.argv[1]
    except IndexError:
        _arg = 'No'
    if _arg.lower() == 'list':
        systemsList()
        return

    # Ages to add to the files.
    ages = np.arange(*map(float, a_range))
    # Add the largest value if it is not included
    if not np.isclose(ages[-1], float(a_range[1])):
        ages = np.append(ages, float(a_range[1]))
    ages = 10. ** ages

    # Sub-folder where isochrone files will be stored. Notice the lower-case
    sub_folder = phot_syst.lower() + '/'

    # If the sub-folder doesn't exist, create it before moving the file.
    full_path = 'isochrones/' + sub_folder
    if not exists(full_path):
        makedirs(full_path)

    print('\nQuery CMD using: {}.'.format(map_models[evol_track][-1]))
    print("Requesting isochrones in the '{}' system.".format(phot_syst))
    track_parsec, track_colibri = map_models[evol_track][:-1]

    # Update parameters in dictionary
    __def_args__['output_gzip'] = (None, gz_flag)
    __def_args__['track_parsec'] = (None, track_parsec)
    __def_args__['track_colibri'] = (None, track_colibri)
    __def_args__['isoc_lagelow'] = (None, a_range[0])
    __def_args__['isoc_lageupp'] = (None, a_range[1])
    __def_args__['isoc_dlage'] = (None, a_range[2])
    __def_args__['photsys_file'] = (
        None, '{}_{}.dat'.format(phot_syst_file, phot_syst))
    __def_args__['photsys_version'] = (None, phot_syst_v)

    # Run for given range in metallicity.
    for i, metal in enumerate(z_range):

        print('\nz = {} ({}/{})'.format(metal, i + 1, len(z_range)))

        # Update metallicity parameter
        par_dict = __def_args__.copy()
        par_dict['isoc_zlow'] = (None, str(metal))

        # Query the service
        data, c = __query_website(par_dict, phot_syst)

        if i == 0:
            filterLambaOmega(c, evol_track, full_path)

        # Add ages to each isochrone
        data = addAge(data, ages, rm_label9)

        # Define file name according to metallicity value.
        file_name = join(full_path + ('%0.6f' % metal).replace('.', '_')
                         + '.dat')

        # Store in file.
        with open(file_name, 'w') as f:
            f.write(data)

    print('\nAll done!')


def systemsList():
    """
    """
    r = requests.get('http://stev.oapd.inaf.it/cgi-bin/cmd')
    soup = BeautifulSoup(r.content, "lxml")
    systs = soup.find_all("select")[0]

    replc = ["""<option value="tab_mag_odfnew/tab_mag_""",
             """<option selected="" value="tab_mag_odfnew/tab_mag_""",
             "</option>", "<i>", "</i>", "<sub>", "</sub>"]

    print("\n{:<40} {}".format("System's ID", "System's name"))
    print("------------------------------------------------------")
    for s in systs:
        sr = str(s)
        for _ in replc:
            sr = sr.replace(_, "")
        sr = [_.strip() for _ in sr.split(""".dat">""")]
        if sr[0] != "":
            print("{:<40} {}".format(sr[0], sr[1]))

    print("\nAll systems listed")


def __query_website(d, phot_syst):
    """
    Communicate with the CMD website.
    """

    print('  Interrogating {0}...'.format(webserver))
    c = requests.post(webserver + '/cgi-bin/cmd', files=d).text
    aa = re.compile('output\d+')
    fname = aa.findall(c)
    if len(fname) > 0:

        url = '{0}/tmp/{1}.dat'.format(webserver, fname[0])
        print('  Downloading data...{0}'.format(url))
        r = requests.get(url)

        typ = gzipDetect(r.content)
        if typ == "gz":
            print("  Compressed 'gz' file detected")
            rr = zlib.decompress(bytes(r.content), 15 + 32).decode('ascii')
        else:
            rr = r.text
        return rr, c
    else:

        error_msg = ("Photometric system {} still not available among YBC "
                     "tables.").format(phot_syst)
        if error_msg in c:
            raise RuntimeError(error_msg)
        else:
            print(c)
            err_i = c.index("errorwarning")
            txt = c[err_i + 17:err_i + 17 + 100]
            print('\n' + txt.split("<br>")[0].replace("</b>", ""), '\n')
            raise RuntimeError('FATAL: Server Response is incorrect')


def filterLambaOmega(c, evol_track, full_path):
    """
    Extract filters, lambdas, and omegas data
    """
    # Extract filters, lambdas, and omegas data
    aa = re.compile('Filter.*<th>&lambda')
    fname = aa.findall(c)
    # In CMD v3.2 apparently all filters have a 'mag' added.
    filters = [
        _.split('</td>')[0] + 'mag' for _ in fname[0].split('<td>')][1:]
    aa = re.compile('lambda.*omega')
    fname = aa.findall(c)
    lambdas = [_.split('</td>')[0] for _ in fname[0].split('<td>')][1:]
    aa = re.compile('omega.*lambda')
    fname = aa.findall(c)
    omegas = [_.split('</td>')[0] for _ in fname[0].split('<td>')][1:]

    # Store in file.
    with open(full_path + "/filterslambdas.dat", 'w') as f:
        f.write(evol_track + "     " + "    ".join(filters + lambdas + omegas))


def gzipDetect(data):
    """
    Detect potential compressed "gz" file.
    """
    gzchars = b"\x1f\x8b\x08"

    if data[:len(gzchars)] == gzchars:
        return "gz"

    return None


def addAge(data, ages, rm_label9):
    """
    The new format in CMD v3.2 does not include the commented line with the
    'Age' value, and the logAge column is rounded to 3 decimal places so
    this value can not be taken from there.

    Add this line back to each age for each metallicity file.
    """

    data = data.split('\n')

    # Indexes of "# Zini" comments
    idx = []
    for i, line in enumerate(data):
        if line.startswith("# Zini"):
            idx.append(i)
    # Insert new comments in their proper positions
    for i, j in enumerate(idx):
        data.insert(j + i, "# Age = {:.6E} yr".format(ages[i]))

    # Remove label=9 indexes. Addresses #2
    if rm_label9:
        idx_9 = []
        for i, line in enumerate(data):
            try:
                if line.split()[9] == '9':
                    idx_9.append(i)
            except IndexError:
                pass
        data = np.delete(data, idx_9).tolist()

    return "\n".join(data)


def readINI():
    """
    Read .ini config file
    """
    in_params = configparser.ConfigParser()
    ini_file = Path("params.not_tracked.ini")
    if not ini_file.is_file():
        ini_file = Path("params.ini")
    in_params.read(ini_file)

    # Data columns
    gz_flag = in_params['Compress'].getboolean('compress')
    evol_track = in_params['Evolutionary tracks'].get('evol_track')
    rm_label9 = in_params['Evolutionary tracks'].getboolean('rm_label9')
    phot_syst = in_params['Photometric system'].get('phot_syst')
    phot_syst_v = in_params['Photometric system'].get('YBC_OBC')
    z_range = in_params['Metallicity / Log(age) ranges'].get('z_range')
    a_range = in_params['Metallicity / Log(age) ranges'].get('a_range')
    z_range = list(map(float, z_range.split()))
    z_range = np.arange(*z_range)
    a_range = a_range.split()

    if evol_track not in map_models.keys():
        raise ValueError("Evolutionary track '{}' is invalid".format(
            evol_track))

    return gz_flag, evol_track, rm_label9, phot_syst, phot_syst_v, z_range,\
        a_range


if __name__ == "__main__":
    main()
