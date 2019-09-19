ezPADOVA-2
==========

A python package that allows you to download PADOVA/PARSEC isochrones directly
from the [CMD](http://stev.oapd.inaf.it/cgi-bin/cmd) website.

Simplified fork of the original [ezpadova](https://github.com/mfouesneau/ezpadova) code by [Morgan Fouesneau](https://github.com/mfouesneau).

Requirements
------------

Uses the `requests`, and `numpy` packages. The latest release can be downloaded [here](https://github.com/asteca/ezpadova-2/releases).

Usage
-----

Evolutionary tracks, photometric system, metallicity and age ranges are set via
the input data file `in_params.dat`.

A list of the proper IDs for the CMD photometric systems ('System ID') can be obtained with the [CMDphotsysts](https://github.com/asteca/CMDphotsysts/) code. You can also just read the latest fetched names [here](https://github.com/asteca/CMDphotsysts/blob/master/CMD_systs_NEW.dat).

The downloaded files are stored in a folder that can be pasted inside the `isochrones/` sub-folder of the `ASteCA` package.
