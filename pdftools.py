#!/usr/bin/env python

import sys
import os as os
import argparse

from tqdm import tqdm
import concurrent.futures
import threading
from time import sleep

import pandoc
from pandoc.types import *
from io import BytesIO

from glob import glob
import re as re
from PyPDF2 import PdfMerger, PdfReader

globMessage = '''
Provide globs instead of paths. Will merge found files in alphanumeric
order.
'''
pandocMessage = '''
Use pandoc to filter out "Organizational Notes" from all documents and
compile to PDF using LaTeX.
'''
interactiveMessage = '''
Prompt user for additional documents' details for the merge.
'''

def getLuaFilter(path=__file__):
    return os.path.join(os.path.dirname(os.path.abspath(path)), "dropOrgNotes.lua")

def map_func(f, xs):
    tmp = []
    for x in xs:
        tmp.append(f(x))
    return tmp

def title_prompt(a,b):
    return f"What should I use for title of {a}? ({b})\n"

def glob_to_files(gs, key=None):
    fs = []
    for g in gs:
        fs += glob(g)
    return sorted(fs, key=key)

def cambridgeSortKey(filename):
    terms = re.split(r'(\.|/|_| )', filename)
    tmp = []
    for t in terms:
        try:
            tmp.append(int(t))
        except ValueError:
            continue
    return tmp

def pdf_cat(input_files, output_path, interactive=False):
    op = os.path.abspath(os.path.expanduser(output_path))
    with PdfMerger() as m:
        bar = tqdm(input_files)
        for input_file in bar:
            bar.set_description(
                f"Found PDF {input_file} with type {type(input_file)}. Attempting merge."
            )
            r = PdfReader(stream=input_file)
            mdata = r.metadata
            title = (mdata.title or input_file)
            if interactive:
                title = str(
                    input(title_prompt(input_file, title))
                    or title)
                bar.set_description(f"Merging {input_file} into {output_path}")
                m.append(fileobj=r, outline_item=title)
        with open(op, "wb") as output_stream:
            m.write(output_stream)

def step_bar(bar, lock):
    i = 0
    lock.acquire(blocking=False)
    while lock.locked():
        sleep(1)
        i += 1
        bar.update()

def pandoc_blocking_action(md, out, l):
    out.append(pandoc.write(md, format="pdf", options=["--citeproc"]))
    l.release()

def run_pandoc(md_file, pb=None):
    new_md = pandoc.read(file=md_file, options=[f"--lua-filter={getLuaFilter()}"])
    outputBytes = [] # Pass by Reference
    l = threading.Lock()
    with tqdm(unit="s", ascii=True, leave=False) as bar:
        t = threading.Thread(
            target=pandoc_blocking_action,
            args=(new_md, outputBytes, l)
        )
        t.start()
        b = threading.Thread(target=step_bar, args=(bar, l))
        bar.set_description(f"Compiling {md_file} to PDF")
        b.start()
        t.join()
        b.join()
        bar.set_description("Done!")
    return outputBytes[0] or None

if __name__ == '__main__':
    parser = argparse.ArgumentParser("pdftools")
    parser.add_argument("files", metavar="PATH",
                        nargs="+", help="Paths of input PDFs")
    parser.add_argument("-g", "--glob", action="store_true",
                        help=globMessage)
    parser.add_argument("-p", "--pandoc", action="store_true",
                        help=pandocMessage)
    parser.add_argument("-i", "--interactive", action="store_true",
                        help=interactiveMessage)

    # Print help if no args are passed
    args = parser.parse_args(args=None if sys.argv[1:] else ['-h'])

    out = input("What is the output path?\n")

    files = None
    if args.glob:
        cambridge = None
        if args.interactive:
            cambridge = str(input("Sort files using Cambridge numbering scheme? (Y/n) [n] "))
        if cambridge == "Y":
            print("Using Cambrdige numbering scheme!")
            files = glob_to_files(args.files, key=cambridgeSortKey)
        else:
            print("Will not use Cambridge numbering scheme!")
            files = glob_to_files(args.files)
    else:
        files = args.files

    print("Here are the PDFs to merge:")
    i = 1
    print("--- START ---")
    for f in files:
        print(f"[{i}] {f}")
        i += 1
        sleep(0.15)
    print("--- END ---")

    input("Press any key to proceed.")

    if args.pandoc:
        with concurrent.futures.ThreadPoolExecutor() as ex:
            pdfBytes = list(
                tqdm(
                    ex.map(run_pandoc, files),
                    total = len(files)
                )
            )
        files = map_func(BytesIO, pdfBytes)
    pdf_cat(files, out, interactive=args.interactive)
