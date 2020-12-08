ezPADOVA-2
==========

A python package to download PARSEC isochrones from the [CMD](http://stev.oapd.inaf.it/cgi-bin/cmd) website. Simplified fork of the original [ezpadova](https://github.com/mfouesneau/ezpadova) code by [Morgan Fouesneau](https://github.com/mfouesneau).



Requirements
------------

Install the requirements in a `conda` environment with:

    $ conda install numpy requests beautifulsoup4 lxml



Usage
-----

Evolutionary tracks, photometric system, metallicity and age ranges are set via
the input data file `in_params.dat`. To run the script, simply use:

    $ python CMD.py

A list of the proper IDs to identify the CMD photometric systems ('System ID') can be obtained calling the script as:

    $ python CMD.py list

The downloaded files are stored in a folder that can be pasted inside the `isochrones/` sub-folder of the `ASteCA` package.
