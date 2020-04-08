"""
This script is based on:

EZPADOVA -- A python package that allows you to download PADOVA isochrones
directly from their website

https://github.com/mfouesneau/ezpadova
"""

import requests
import zlib
import re
import numpy as np
from os.path import join, exists
from os import makedirs

# Available sets of tracks (PARSEC + COLIBRI).
map_models = {
    'PAR12_35': ('parsec_CAF09_v1.2S', 'parsec_CAF09_v1.2S_S35',
                 'PARSEC v1.2S + COLIBRI S_35'),
    'PAR12_07': ('parsec_CAF09_v1.2S', 'parsec_CAF09_v1.2S_S07',
                 'PARSEC v1.2S + COLIBRI S_07'),
    'PAR12_16': ('parsec_CAF09_v1.2S', 'parsec_CAF09_v1.2S_NOV13',
                 'PARSEC v1.2S + COLIBRI PR16'),
    'PAR12_N': ('parsec_CAF09_v1.2S', 'no', 'PARSEC v1.2S + No'),
    'PAR11': ('parsec_CAF09_v1.1', '', 'PARSEC v1.1'),
    'PAR10': ('parsec_CAF09_v1.0', '', 'PARSEC v1.0')
}

__def_args__ = {
    "submit_form": (None, "Submit"),
    "cmd_version": (None, "3.2"),
    "track_postagb": (None, "no"),
    "n_inTPC": (None, "10"),
    "eta_reimers": (None, "0.2"),
    "kind_interp": (None, "1"),
    "kind_postagb": (None, "-1"),
    "photsys_version": (None, "YBC"),
    "dust_sourceM": (None, "dpmod60alox40"),
    "dust_sourceC": (None, "AMCSIC15"),
    "kind_mag": (None, "2"),
    "kind_dust": (None, "0"),
    "extinction_av": (None, "0.0"),
    "extinction_coeff": (None, "constant"),
    "extinction_curve": (None, "cardelli"),
    'imf_file': (None, "tab_imf/imf_kroupa_orig.dat"),
    "isoc_isagelog": (None, "1"),
    "isoc_ismetlog": (None, "0"),
    "isoc_zupp": (None, "0.03"),
    "isoc_dz": (None, "0.0"),
    "output_kind": (None, "0"),
    "output_evstage": (None, "1"),
    "lf_maginf": (None, "-15"),
    "lf_magsup": (None, "20"),
    "lf_deltamag": (None, "0.5"),
    "sim_mtot": (None, "1.0e4")}


def main():

    # Read input parameters from file.
    evol_track, phot_syst, z_range, a_vals = read_params()
    # Ages to add to the files.
    ages = np.arange(*map(float, a_vals))
    # Add the largest value if it is not included
    if not np.isclose(ages[-1], float(a_vals[1])):
        ages = np.append(ages, float(a_vals[1]))
    ages = 10. ** ages

    # Map isochrones set selection to proper name.
    iso_sys = {
        'PAR12_N': 'parsec12', 'PAR12_16': 'parsec1216',
        'PAR12_07': 'parsec1207', 'PAR12_35': 'parsec1235',
        'PAR11': 'parsec11', 'PAR10': 'parsec10'}
    # Sub-folder where isochrone files will be stored.
    sub_folder = iso_sys[evol_track] + '_' + phot_syst + '/'

    # If the sub-folder doesn't exist, create it before moving the file.
    full_path = 'isochrones/' + sub_folder
    if not exists(full_path):
        makedirs(full_path)

    print('\nQuery CMD using: {}.'.format(map_models[evol_track][-1]))
    print("Requesting isochrones in the '{}' system.".format(phot_syst))

    track_parsec, track_colibri = map_models[evol_track][:-1]
    # Run for given range in metallicity.
    for i, metal in enumerate(z_range):

        print('\nz = {} ({}/{})'.format(metal, i + 1, len(z_range)))

        # Define isochrones' parameters
        par_dict = isoch_params(
            a_vals, metal, track_parsec, track_colibri, phot_syst)

        # Query the service
        data = __query_website(par_dict)

        # Add ages to each isochrone
        data = addAge(data, ages)

        # Define file name according to metallicity value.
        file_name = join(full_path + ('%0.6f' % metal).replace('.', '_') +
                         '.dat')

        # Store in file.
        with open(file_name, 'w') as f:
            f.write(data)

    print('\nAll done.')


def read_params():
    """
    Read input parameters from file.
    """

    # Accept these variations of the 'true' flag.
    true_lst = ('True', 'true', 'TRUE')

    with open('in_params.dat', 'r') as f:
        # Iterate through each line in the file.
        for line in f:

            if not line.startswith("#") and line.strip() != '':
                reader = line.split()

                # Tracks.
                if reader[0] == 'ET':
                    evol_track = str(reader[1])

                # Photometric system.
                if reader[0] == 'PS':
                    phot_syst = str(reader[1])

                # Metallicity range/values.
                if reader[0] == 'MR':
                    z_vals = list(map(float, reader[1:4]))
                    z_range = np.arange(*z_vals)
                if reader[0] == 'MV':
                    if reader[1] in true_lst:
                        z_range = list(map(float, reader[2:]))

                # Age range.
                if reader[0] == 'AR':
                    a_vals = reader[1:4]

    return evol_track, phot_syst, z_range, a_vals


def isoch_params(a_vals, metal, track_parsec, track_colibri, phot_syst):
    """
    Define parameters in dictionary
    """
    d = __def_args__.copy()

    d['track_parsec'] = (None, track_parsec)
    d['track_colibri'] = (None, track_colibri)

    d['isoc_zlow'] = (None, str(metal))
    logt0, logt1, dlogt = a_vals
    d['isoc_lagelow'] = (None, logt0)
    d['isoc_lageupp'] = (None, logt1)
    d['isoc_dlage'] = (None, dlogt)

    # d['imf_file'] = (None, map_imfs[imf_sel])
    d['photsys_file'] = (
        None, 'tab_mag_odfnew/tab_mag_{0}.dat'.format(phot_syst))

    return d


def __query_website(d):
    """
    Communicate with the CMD website.
    """

    webserver = 'http://stev.oapd.inaf.it'
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
        return rr
    else:
        print(c)
        err_i = c.index("errorwarning")
        txt = c[err_i + 17:err_i + 17 + 100]
        print('\n' + txt.split("<br>")[0].replace("</b>", ""), '\n')
        raise RuntimeError('FATAL: Server Response is incorrect')


def gzipDetect(data):
    """
    Detect potential compressed "gz" file.
    """
    gzchars = b"\x1f\x8b\x08"

    if data[:len(gzchars)] == gzchars:
        return "gz"

    return None


def addAge(data, ages):
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

    return "\n".join(data)


if __name__ == "__main__":
    main()
