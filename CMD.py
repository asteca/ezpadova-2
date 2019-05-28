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

# Available IMF models.
map_imfs = {
    'salpeter': ('tab_imf/imf_salpeter.dat'),
    'chab_exp': ('tab_imf/imf_chabrier_exponential.dat'),
    'chab_log': ('tab_imf/imf_chabrier_lognormal.dat'),
    'chab_log_sal': ('tab_imf/imf_chabrier_lognormal_salpeter.dat'),
    'kroupa': ('tab_imf/imf_kroupa_orig.dat')
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
    evol_track, imf_sel, phot_syst, z_range, a_vals = read_params()

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
    print("Requesting isochrones in the '{}' system.\n".format(phot_syst))

    track_parsec, track_colibri = map_models[evol_track][:-1]
    # Run for given range in metallicity.
    for metal in z_range:

        print('z = {}'.format(metal))
        # Call function to get isochrones.
        r = get_t_isochrones(
            a_vals, metal, track_parsec, track_colibri, imf_sel, phot_syst)

        # Define file name according to metallicity value.
        file_name = join(full_path + ('%0.6f' % metal).replace('.', '_') +
                         '.dat')

        # Store in file.
        with open(file_name, 'w') as f:
            f.write(r)

    print('\nAll done.')


def get_t_isochrones(
        a_vals, metal, track_parsec, track_colibri, imf_sel, phot_syst):
    """
    Get a sequence of isochrones at constant Z.
    """
    d = __def_args__.copy()

    d['track_parsec'] = (None, track_parsec)
    d['track_colibri'] = (None, track_colibri)

    d['isoc_zlow'] = (None, str(metal))
    logt0, logt1, dlogt = a_vals
    d['isoc_lagelow'] = (None, logt0)
    d['isoc_lageupp'] = (None, logt1)
    d['isoc_dlage'] = (None, dlogt)

    d['imf_file'] = (None, map_imfs[imf_sel])
    d['photsys_file'] = (
        None, 'tab_mag_odfnew/tab_mag_{0}.dat'.format(phot_syst))

    r = __query_website(d)

    return r


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
        r = requests.get(url).text
        typ = file_type(r, stream=True)
        if typ is not None:
            r = zlib.decompress(bytes(r), 15 + 32)
        return r
    else:
        print(c)
        err_i = c.index("errorwarning")
        txt = c[err_i + 17:err_i + 17 + 100]
        print('\n' + txt.split("<br>")[0].replace("</b>", ""), '\n')
        raise RuntimeError('FATAL: Server Response is incorrect')


def read_params():
    '''
    Read input parameters from file.
    '''

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

                # Initial mass function.
                if reader[0] == 'IF':
                    imf_sel = str(reader[1])

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

    return evol_track, imf_sel, phot_syst, z_range, a_vals


def file_type(filename, stream=False):
    """ Detect potential compressed file
    Returns the gz, bz2 or zip if a compression is detected, else None.
    """
    magic_dict = {
        "\x1f\x8b\x08": "gz",
        "\x42\x5a\x68": "bz2",
        "\x50\x4b\x03\x04": "zip"
    }
    max_len = max(len(x) for x in magic_dict)
    if not stream:
        with open(filename) as f:
            file_start = f.read(max_len)
        for magic, filetype in magic_dict.items():
            if file_start.startswith(magic):
                return filetype
    else:
        for magic, filetype in magic_dict.items():
            if filename[:len(magic)] == magic:
                return filetype

    return None


if __name__ == "__main__":
    main()
