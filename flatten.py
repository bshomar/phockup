import os
import shutil
import sys


inputdir = r'Y:\2010'
outdir = r'Y:\2010-flat'

if not os.path.exists(outdir):
    os.mkdir(outdir)

for root, _, files in os.walk(inputdir):
    for filename in files:
        source_file = os.path.join(root,filename)
        target_file_name = os.path.basename(filename)
        target_file = os.path.join(outdir,target_file_name)
        index = 1
        while os.path.exists(target_file):
            index += 1
            name, ext = os.path.splitext(target_file)
            name += '-%s' % index
            target_file = name + ext
        shutil.move(source_file, target_file)
        print("mv %s --> %s" % (source_file, target_file))

print('Done')
