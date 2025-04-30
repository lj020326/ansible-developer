#!/usr/bin/env python3

import os
import sys
import argparse
from argparse import RawTextHelpFormatter
import logging
import logging.handlers

from pdf2image import convert_from_path
from PIL import Image

# requirements:
# pip install pillow pdf2image

# __scriptName__ = sys.argv[0]
__scriptName__ = os.path.basename(sys.argv[0])

__version__ = '2025.4.15'
__updated__ = '15 Apr 2025'

progname = __scriptName__.split(".")[0]

# loglevel - logging.DEBUG
loglevel = logging.INFO

log = logging.getLogger(__scriptName__)
log.setLevel(loglevel)

## create console handler
handler = logging.StreamHandler()
# handler.setLevel(logging.DEBUG)
log.addHandler(handler)


def convert_pdf_to_image_pdf(pdf_path, output_path, dpi=300):
    """
    Converts a PDF file to an image-based PDF using Pillow.

    Args:
        pdf_path (str): Path to the input PDF file.
        output_path (str): Path to save the output image-based PDF file.
        dpi (int, optional): Resolution for converting PDF pages to images. Defaults to 300.
    """
    images = convert_from_path(pdf_path, dpi=dpi)
    if images:
        images[0].save(output_path, "PDF", resolution=100.0, save_all=True, append_images=images[1:])
    else:
        print("Error: No pages found in PDF or conversion failed.")


# ------------------------------------------------------
# Name: main()
# Role: parse CLI args and call function to add/update/remove/list tomcat datasources
# ------------------------------------------------------

def main(argv):

    prog_usage = '''
requires the python library 'pdf2image' and poppler to be installed
ref: https://pdf2image.readthedocs.io/en/latest/installation.html

Examples of use:

{0} input.pdf output.pdf
{0} -l DEBUG input.pdf output.pdf

'''.format(__scriptName__)

    parser = argparse.ArgumentParser(formatter_class=RawTextHelpFormatter,
                                     description="Use this script convert pdf to image based pdf",
                                     epilog=prog_usage)

    group = parser.add_mutually_exclusive_group()
    group.add_argument("-l", "--loglevel", choices=['DEBUG', 'INFO', 'WARN', 'ERROR'], help="log level")
    group.add_argument("-d", "--dpi", help="dpi (e.g., 300, 600)")

    parser.add_argument('input_pdf_file_path',
                        help="Specify input pdf file path to convert to image based pdf")
    parser.add_argument('output_pdf_file_path',
                        help="Specify output pdf file path")

    # parser.add_argument('args', nargs=argparse.REMAINDER)
    # parser.add_argument('args', nargs='?')
    # parser.parse_args()

    args, additional_args = parser.parse_known_args()

    if args.loglevel:
        log.setLevel(args.loglevel)
        log.debug("set loglevel to [%s]" % loglevel)

    log.debug("started")

    if additional_args:
        log.debug("additional args=%s" % additional_args)

    log.debug("args.input_pdf_file_path [%s]" % args.input_pdf_file_path)
    log.debug("args.output_pdf_file_path [%s]" % args.output_pdf_file_path)
    convert_pdf_to_image_pdf(args.input_pdf_file_path, args.output_pdf_file_path, args.dpi)

    # if args.dpi:
    #     convert_pdf_to_image_pdf(args.input_pdf_file_path, args.output_pdf_file_path, args.dpi)
    # else:
    #     convert_pdf_to_image_pdf(args.input_pdf_file_path, args.output_pdf_file_path)

    log.debug("finished")


# ------------------------------------------
# Code Execution begins
# ------------------------------------------
if (__name__ == '__main__') or (__name__ == 'main'):
    # main(sys.argv[1:])
    main(sys.argv)
else:
    log.error("This script should be executed, not imported.")

