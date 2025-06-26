#!/usr/bin/env python3

import os
import sys
import argparse
from argparse import RawTextHelpFormatter
import logging
import logging.handlers

from pdf2image import convert_from_path
from pdf2image import pdfinfo_from_path
# from pdf2image.exceptions import (
# PDFInfoNotInstalledError,
# PDFPageCountError,
# PDFSyntaxError
# )

from PIL import Image

# requirements:
# pip install pillow pdf2image

# __scriptName__ = sys.argv[0]
__scriptName__ = os.path.basename(sys.argv[0])

__version__ = '2025.6.25'
__updated__ = '25 June 2025'

progname = __scriptName__.split(".")[0]

# loglevel - logging.DEBUG
loglevel = logging.INFO

log = logging.getLogger(__scriptName__)
log.setLevel(loglevel)

## create console handler
handler = logging.StreamHandler()
# handler.setLevel(logging.DEBUG)
log.addHandler(handler)

## ref: https://stackoverflow.com/a/66553407/2791368
poppler_path = "/usr/local/Cellar/poppler/25.06.0/bin"


def convert_pdf_to_image_pdf(pdf_path, output_path, dpi=400):
    """
    Converts a PDF file to an image-based PDF using Pillow.

    Args:
        pdf_path (str): Path to the input PDF file.
        output_path (str): Path to save the output image-based PDF file.
        dpi (int, optional): Resolution for converting PDF pages to images. Defaults to 300.
    """

    page_count = pdfinfo_from_path(pdf_path)["Pages"]
    log.debug("page_count: "+str(page_count))
    if log.level == logging.DEBUG:
        try:
            # pdf_info = pdfinfo_from_path(pdf_path, poppler_path=poppler_path)
            pdf_info = pdfinfo_from_path(pdf_path)

            print("PDF Information:")
            for key, value in pdf_info.items():
                print(f"\t{key}: {value}")

        except Exception as e:
            print(f"Error getting PDF information: {e}")

    # images = convert_from_path(pdf_path, dpi=dpi, poppler_path=poppler_path)
    # images = convert_from_path(pdf_path, dpi=dpi, fmt="jpeg")
    # images = convert_from_path(pdf_path, dpi=dpi)
    images = convert_from_path(pdf_path)
    if images:
        images[0].save(output_path,
                       poppler_path=poppler_path,
                       format="PDF",
                       resolution=100.0,
                       save_all=True,
                       append_images=images[1:])
    else:
        log.error("Error: No pages found in PDF or conversion failed.")


# ------------------------------------------------------
# Name: main()
# Role: parse CLI args and call function to add/update/remove/list tomcat datasources
# ------------------------------------------------------

def main(argv):

    prog_usage = '''
requires the python library 'pdf2image' and 'poppler' to be installed
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

