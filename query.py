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
    'PARSEC': {
        'PAR20': 'parsec_CAF09_v2.0',
        'PAR12S': 'parsec_CAF09_v1.2S',
        'PAR11': 'parsec_CAF09_v1.1',
        'PAR10': 'parsec_CAF09_v1.0'
    },
    'COLIBRI': {
        'S_37': 'parsec_CAF09_v1.2S_S_LMC_08_web',
        'S_35': 'parsec_CAF09_v1.2S_S35',
        'S_07': 'parsec_CAF09_v1.2S_S07',
        'PR16': 'parsec_CAF09_v1.2S_NOV13',
        'No': 'no',
    }
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
    "track_omegai": (None, "0.00"),
    "track_postagb": (None, "no"),
    # "n_inTPC": (None, "10"),
    # "eta_reimers": (None, "0.2"),
    "photsys_version": (None, "YBCnewVega"),
    "dust_sourceM": (None, "dpmod60alox40"),
    "dust_sourceC": (None, "AMCSIC15"),
    "extinction_coeff": (None, "constant"),
    "extinction_curve": (None, "cardelli"),
    "kind_LPV": (None, "1"),
    "isoc_isagelog": (None, "1"),  # log(age)
    "isoc_ismetlog": (None, "0"),  # Z
    "output_kind": (None, "0"),
    'imf_file': (None, "tab_imf/imf_kroupa_orig.dat")
}

# IMPORTANT!!!
# This root is important, it will change from time to time and some systems
# appear to be missing the 'YBC' at the beginning
phot_syst_file = 'YBC_tab_mag_odfnew/tab_mag'


def main():
    """
    Use with :

    $ python query.py list

    to list all available photometric systems.
    """

    # Read input parameters from file.
    gz_flag, PARSEC, COLIBRI, rm_label9, omegai, phot_syst, phot_syst_v,\
        met_sel, age_sel, m_range, a_range = readINI()

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
    if age_sel == 'log':
        ages = 10. ** ages

    # Sub-folder where isochrone files will be stored. Notice the lower-case
    sub_folder = phot_syst.lower() + '/'

    # If the sub-folder doesn't exist, create it before moving the file.
    full_path = 'isochrones/' + sub_folder
    if not exists(full_path):
        makedirs(full_path)

    print('\nQuery CMD using: {} + COLIBRI {}.'.format(
        PARSEC, COLIBRI))
    print("Requesting isochrones in the '{}' system.".format(phot_syst))
    track_parsec = map_models['PARSEC'][PARSEC]
    track_colibri = map_models['COLIBRI'][COLIBRI]
    evol_track = PARSEC + '+C' + COLIBRI

    # Update parameters in dictionary
    __def_args__['output_gzip'] = (None, gz_flag)
    __def_args__['track_parsec'] = (None, track_parsec)
    __def_args__['track_omegai'] = (None, omegai)
    __def_args__['track_colibri'] = (None, track_colibri)

    if age_sel == 'log':
        __def_args__['isoc_lagelow'] = (None, a_range[0])
        __def_args__['isoc_lageupp'] = (None, a_range[1])
        __def_args__['isoc_dlage'] = (None, a_range[2])
    elif age_sel == 'linear':
        __def_args__['isoc_isagelog'] = (None, "0")
        __def_args__['isoc_agelow'] = (None, a_range[0])
        __def_args__['isoc_ageupp'] = (None, a_range[1])
        __def_args__['isoc_dage'] = (None, a_range[2])

    if met_sel == 'MH':
        __def_args__['isoc_ismetlog'] = (None, "1")

    __def_args__['photsys_file'] = (
        None, '{}_{}.dat'.format(phot_syst_file, phot_syst))
    __def_args__['photsys_version'] = (None, phot_syst_v)

    # Run for given range in metallicity.
    for i, metal in enumerate(m_range):

        print('\nz = {} ({}/{})'.format(metal, i + 1, len(m_range)))

        # Update metallicity parameter
        par_dict = __def_args__.copy()
        if met_sel == 'Z':
            par_dict['isoc_zlow'] = (None, str(metal))
        elif met_sel == 'MH':
            par_dict['isoc_metlow'] = (None, str(metal))

        # Query the service
        data, c = __query_website(par_dict, phot_syst)

        if i == 0:
            filterLambaOmega(c, evol_track, full_path)

        # Add ages to each isochrone
        data = addAge(data, ages, rm_label9)

        if met_sel == 'MH':
            metal = MHtoZ(metal)

        # Define file name according to metallicity value.
        file_name = join(full_path + ('%0.10f' % metal).replace('.', '_')
                         + '.dat')

        # Store in file.
        with open(file_name, 'w') as f:
            f.write(data)

    print('\nAll done!')


def MHtoZ(MH):
    """
    Transform the MH metallicity values to Z using the relation given
    in the CMD service:

    [M/H]=log(Z/X)-log(Z/X)_o,
    with (Z/X)_o=0.0207 and Y=0.2485+1.78Z for PARSEC tracks.
    """
    a, b, c = 0.2485, 1.78, np.log10(0.0207)
    Z = (1 - a) / (10**(-(MH + c)) + b + 1)
    return Z


def systemsList():
    """
    """
    r = requests.get('http://stev.oapd.inaf.it/cgi-bin/cmd')
    soup = BeautifulSoup(r.content, "lxml")
    systs = soup.find_all("select")[0]

    # replc = ["""<option value="tab_mag_odfnew/tab_mag_""",
    #          """<option selected="" value="tab_mag_odfnew/tab_mag_""",
    #          "</option>", "<i>", "</i>", "<sub>", "</sub>"]

    print("\n{:<40} {}".format("System's ID", "System's name"))
    print("------------------------------------------------------")
    for s in systs:
        s = str(s)
        if 'tab_mag_' in s:
            s = s.split('/tab_mag_')[1]
            sr = [_.strip() for _ in s.split(""".dat">""")]
            if sr[0] != "" and len(sr) > 1:
                print(
                    "{:<40} {}".format(sr[0], sr[1].replace('</option>', '')))

        # sr = str(s)
        # for _ in replc:
        #     sr = sr.replace(_, "")
        # sr = [_.strip() for _ in sr.split(""".dat">""")]
        # if sr[0] != "":
        #     print("{:<40} {}".format(sr[0], sr[1]))

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
    PARSEC = in_params['Evolutionary tracks'].get('PARSEC')
    COLIBRI = in_params['Evolutionary tracks'].get('COLIBRI')
    rm_label9 = in_params['Evolutionary tracks'].getboolean('rm_label9')
    omegai = in_params['Photometric system'].get('omegai')
    phot_syst = in_params['Photometric system'].get('phot_syst')
    phot_syst_v = in_params['Photometric system'].get('YBC_OBC')

    met_sel = in_params['Metallicity / Age ranges'].get('met_selection')
    age_sel = in_params['Metallicity / Age ranges'].get('age_selection')
    m_range = in_params['Metallicity / Age ranges'].get('met_range')
    a_range = in_params['Metallicity / Age ranges'].get('age_range')
    m_range = list(map(float, m_range.split()))
    m_range = np.arange(*m_range)
    a_range = a_range.split()

    if PARSEC not in map_models['PARSEC'].keys():
        raise ValueError("Evolutionary track '{}' is invalid".format(
            PARSEC))

    return gz_flag, PARSEC, COLIBRI, rm_label9, omegai, phot_syst,\
        phot_syst_v, met_sel, age_sel, m_range, a_range


if __name__ == "__main__":
    main()
