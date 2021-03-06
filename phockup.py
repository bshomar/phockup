#!/usr/bin/env python3
import getopt
import hashlib
import os
import shutil
import sys
import re
import logging
from datetime import datetime
from subprocess import check_output, CalledProcessError
from progress import ProgressBar

version = '1.4.0'


def main(argv):
    check_dependencies()

    move_files = False
    date_regex = None
    log_fname = None
    sha_rename = False
    dir_format = os.path.sep.join(['%Y', '%m', '%d'])

    try:
        opts, args = getopt.getopt(argv[2:], "d:r:l:mhs", ["date=", "regex=", "log=", "move", "help","sha-rename"])
    except getopt.GetoptError as e:
        print(e)
        help_info()

    for opt, arg in opts:
        if opt in ("-h", "--help"):
            print('Printing help:')
            help_info()

        if opt in ("-d", "--date"):
            if not arg:
                print('Date format cannot be empty')
                sys.exit(0)
            dir_format = parse_date_format(arg)

        if opt in ("-l", "--log"):
            if not arg:
                print("log file name can't be empty")
                sys.exit(0)
            log_fname = arg

        if opt in ("-m", "--move"):
            move_files = True
            print('Using move strategy!')

        if opt in ("-s", "--sha-rename"):
            sha_rename = True
            print('Renaming files to SHA256 name!')

        if opt in ("-r", "--regex"):
            try:
                date_regex = re.compile(arg)
            except:
                error("Provided regex is invalid!")

    if len(argv) < 2:
        print('ERROR: Number of arguments are less than 2')
        print(argv)
        help_info()

    inputdir = os.path.expanduser(argv[0])
    outputdir = os.path.expanduser(argv[1])

    if not os.path.isdir(inputdir) or not os.path.exists(inputdir):
        error('Input directory "%s" does not exist or cannot be accessed' % inputdir)
    if not os.path.exists(outputdir):
        print('Output directory "%s" does not exist, creating now' % outputdir)
        try:
            os.makedirs(outputdir)
        except Exception:
            print('Cannot create output directory. No write access!')
            sys.exit(0)

    if log_fname:
        logging.basicConfig(filename=log_fname, level='DEBUG')
    else:
        logging.basicConfig(level='CRITICAL')

    ignored_files = ('.DS_Store', 'Thumbs.db')
    error_list = list()
    count = dict(copied=0, moved=0, duplicate=0, error=0, other=0 )
    total_count=0
    for _, _, files in os.walk(inputdir): total_count += len(files)
    bar = ProgressBar(total_count, count.keys())
    for root, _, files in os.walk(inputdir):
        for filename in files:
            try:
                if filename in ignored_files:
                    continue
                if not sha_rename:
                    status = handle_file(os.path.join(root, filename), outputdir, dir_format, move_files, date_regex)
                else:
                    status = handle_file2(os.path.join(root, filename), outputdir, dir_format, move_files, date_regex)
                count[status] += 1
                bar.increment(status)
            except KeyboardInterrupt:
                print('\n Exiting...')
                print_summary(count)
                sys.exit(0)
            except Exception as e :
                logging.error('Error skipping %s:%s' % (filename,repr(e)))
                error_list.append(os.path.join(root, filename))
                count['error'] += 1
                bar.increment('error')
    bar.done()
    logging.info('===Files with Errors===')
    for fn in error_list:
        logging.info(fn)
    logging.info('===End Files with Errors===')
    print_summary(count)

def print_summary(summary: dict):
    total = sum(summary.values())
    logging.info('%s:\t%s\t%.0f%%' % ('total', total, 100.0))
    print('%s:\t%s\t%.0f%%' % ('total', total, 100.0))
    for key,value in summary.items():
        logging.info('%s:\t%s\t%.0f%%' % (key,value,100*value/total))
        print('%s:\t%s\t%.0f%%' % (key, value, 100 * value / total))



def check_dependencies():
    if shutil.which('exiftool') is None:
        print('Exiftool is not installed. Visit http://www.sno.phy.queensu.ca/~phil/exiftool/')
        sys.exit(2)


def parse_date_format(date):
    date = date.replace("YYYY", "%Y")  # 2017 (year)
    date = date.replace("YY", "%y")    # 17 (year)
    date = date.replace("m", "%b")     # Dec (month)
    date = date.replace("MM", "%m")    # 12 (month)
    date = date.replace("M", "%B")     # December (month)
    date = date.replace("DDD", "%j")   # 123 (day or year)
    date = date.replace("DD", "%d")    # 25 (day)
    date = date.replace("\\", os.path.sep)  # path separator
    date = date.replace("/", os.path.sep)   # path separator
    return date


def exif(file):
    try:
        data = check_output(['exiftool', file]).decode('UTF-8',"ignore").strip().split("\\n")[0].split("\n")
        exif_data = {}
    except (CalledProcessError, UnicodeDecodeError):
        return None

    for row in data:
        opt = row.split(":")
        exif_data[opt[0].strip()] = ":".join(opt[1:]).strip()

    return exif_data


def get_date(file, exif_data, user_regex=None, use_modification_date=False):
    keys = ['Create Date', 'Date/Time Original', 'Media created']
    if use_modification_date:
        keys.append('File Modification Date/Time')
    datestr = None

    for key in keys:
        if key in exif_data:
            datestr = exif_data[key]
            break

    if datestr:
        datestr = datestr.split('.')
        date = datestr[0]

        if len(datestr) > 1:
            subseconds = datestr[1]
        else:
            subseconds = ''

        search = r'(.*)([+-]\d{2}:\d{2})'
        if re.search(search, date) is not None:
            date = re.sub(search, r'\1', date)

        try:
            parsed_date_time = datetime.strptime(date, "%Y:%m:%d %H:%M:%S")
        except ValueError:
            try:
                parsed_date_time = datetime.strptime(date, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                parsed_date_time = None

        return {
            'date': parsed_date_time,
            'subseconds': subseconds
        }
    else:
        # If missing datetime from EXIF data check if filename is in datetime format.
        # For this use a user provided regex if possible.
        # Otherwise assume a filename such as IMG_20160915_123456.jpg as default.
        default_regex = re.compile('.*[_-](?P<year>\d{4})(?P<month>\d{2})(?P<day>\d{2})[_-]?(?P<hour>\d{2})(?P<minute>\d{2})(?P<second>\d{2})')
        regex = user_regex or default_regex
        matches = regex.search(os.path.basename(file))

        if matches:
            try:
                match_dir = matches.groupdict()
                match_dir = dict([a, int(x)] for a, x in match_dir.items()) #Convert str to int
                date = datetime(
                    match_dir["year"], match_dir["month"], match_dir["day"],
                    match_dir["hour"], match_dir["minute"], match_dir["second"]
                )
            except (KeyError, ValueError):
                date = None

            if date:
                return {
                    'date': date,
                    'subseconds': ''
                }


def get_output_dir(date, outputdir, dir_format):
    if outputdir.endswith(os.path.sep):
        outputdir = outputdir[:-1]

    try:
        path = [
            outputdir,
            date['date'].date().strftime(dir_format)
        ]
    except:
        path = [
            outputdir,
            'unknown',
        ]

    fullpath = os.path.sep.join(path)

    if not os.path.isdir(fullpath):
        try:
            os.makedirs(fullpath)
        except Exception:
            print('')
            print('Cannot create directory %s. No write access!' % fullpath)
            sys.exit(0)

    return fullpath


def get_file_name(file, date):
    try:
        filename = [
            '%04d' % date['date'].year,
            '%02d' % date['date'].month,
            '%02d' % date['date'].day,
            '-',
            '%02d' % date['date'].hour,
            '%02d' % date['date'].minute,
            '%02d' % date['date'].second,
        ]

        if date['subseconds']:
            filename.append(date['subseconds'])

        return ''.join(filename) + os.path.splitext(file)[1]

    except:
        return os.path.basename(file)


def is_image_or_video(exif_data):
    pattern = re.compile('^(image/.+|video/.+|application/vnd.adobe.photoshop)$')
    if exif_data and pattern.match(exif_data['MIME Type']):
        return True
    return False


def handle_file(source_file, outputdir, dir_format, move_files, date_regex=None):
    if str.endswith(source_file, '.xmp'):
        return 'other'

    status = 'other'
    info = source_file
    #print(source_file, end="", flush=True)

    exif_data = exif(source_file)

    if exif_data and is_image_or_video(exif_data):
        date = get_date(source_file, exif_data, date_regex)
        output_dir = get_output_dir(date, outputdir, dir_format)
        target_file_name = get_file_name(source_file, date).lower()
        target_file_path = os.path.sep.join([output_dir, target_file_name])
    else:
        output_dir = get_output_dir(False, outputdir, dir_format)
        target_file_name = os.path.basename(source_file)
        target_file_path = os.path.sep.join([output_dir, target_file_name])

    suffix = 1
    target_file = target_file_path
    while True:
        if os.path.isfile(target_file):
            if sha256_checksum(source_file) == sha256_checksum(target_file):
                info += ' => skipped, duplicated file'
                status = 'duplicate'
                break
        else:
            if move_files:
                shutil.move(source_file, target_file)
                status = 'moved'
            else:
                shutil.copy2(source_file, target_file)
                status = 'copied'

            info += ' => %s' % target_file
            handle_file_xmp(source_file, target_file_name, suffix, output_dir, move_files)
            break

        suffix += 1
        target_split = os.path.splitext(target_file_path)
        target_file = "%s-%d%s" % (target_split[0], suffix, target_split[1])
    logging.info(info)
    return status

def handle_file2(source_file, outputdir, dir_format, move_files, date_regex=None):
    """
    rename files to sha256 name and put them in the unknown directory
    """
    status = 'other'
    info = source_file
    #print(source_file, end="", flush=True)

    exif_data = exif(source_file)


    target_file_name = os.path.basename(source_file)
    source_sha256 = sha256_checksum(source_file)
    if is_image_or_video(exif_data):
        date = get_date(source_file, exif_data, date_regex, True)
        output_dir = get_output_dir(date, outputdir, dir_format)
        base, ext = os.path.splitext(target_file_name)
        target_file_name = source_sha256 + ext
    else:
        output_dir = get_output_dir(False, outputdir, dir_format)
    target_file = os.path.sep.join([output_dir, target_file_name])

    if os.path.isfile(target_file):
        info += ' => skipped, duplicated file'
        status = 'duplicate'
    else:
        if move_files:
            shutil.move(source_file, target_file)
            status = 'moved'
        else:
            shutil.copy2(source_file, target_file)
            status = 'copied'

    info += ' => %s' % target_file
    logging.info(info)
    return status


def handle_file_xmp(source_file, photo_name, suffix, exif_output_dir, move_files):
    xmp_original_with_ext = source_file + '.xmp'
    xmp_original_without_ext = os.path.splitext(source_file)[0] + '.xmp'

    suffix = '-%s' % suffix if suffix > 1 else ''

    if os.path.isfile(xmp_original_with_ext):
        xmp_original = xmp_original_with_ext
        xmp_target = '%s%s.xmp' % (photo_name, suffix)
    elif os.path.isfile(xmp_original_without_ext):
        xmp_original = xmp_original_without_ext
        xmp_target = '%s%s.xmp' % (os.path.splitext(photo_name)[0], suffix)
    else:
        xmp_original = None
        xmp_target = None

    if xmp_original:
        xmp_path = os.path.sep.join([exif_output_dir, xmp_target])
        logging.info('%s => %s' % (xmp_original, xmp_path))

        if move_files:
            shutil.move(xmp_original, xmp_path)
        else:
            shutil.copy2(xmp_original, xmp_path)


def sha256_checksum(filename, block_size=65536):
    sha256 = hashlib.sha256()
    with open(filename, 'rb') as f:
        for block in iter(lambda: f.read(block_size), b''):
            sha256.update(block)
    return sha256.hexdigest()


def error(message):
    print(message)
    sys.exit(2)


def help_info():
    error("""NAME
    phockup - v{version}

SYNOPSIS
    phockup INPUTDIR OUTPUTDIR [OPTIONS]

DESCRIPTION
    Media sorting tool to organize photos and videos from your camera in folders by year, month and day.
    The software will collect all files from the input directory and copy them to the output directory without
    changing the files content. It will only rename the files and place them in the proper directory for year, month and day.

ARGUMENTS
    INPUTDIR
        Specify the source directory where your photos are located

    OUTPUTDIR
        Specify the output directory where your photos should be exported

OPTIONS
    -d | --date
        Specify date format for OUTPUTDIR directories.
        You can choose different year format (e.g. 17 instead of 2017) or decide
        to skip the day directories and have all photos sorted in year/month.

        Supported formats:
            YYYY - 2016, 2017 ...
            YY   - 16, 17 ...
            MM   - 07, 08, 09 ...
            M    - July, August, September ...
            m    - Jul, Aug, Sept ...
            DD   - 27, 28, 29 ... (day of month)
            DDD  - 123, 158, 365 ... (day of year)

        Example:
            YYYY/MM/DD -> 2011/07/17
            YYYY/M/DD  -> 2011/July/17
            YYYY/m/DD  -> 2011/Jul/17
            YY/m-DD    -> 11/Jul-17

    -s | --sha-rename
        rename all files to the SHA256 key - used mainly as a second pass to clean the unknown directory

    -h | --help
        Display this help.

    -m | --move
        Instead of copying the process will move all files from the INPUTDIR to the OUTPUTDIR.
        This is useful when working with a big collection of files and the
        remaining free space is not enough to make a copy of the INPUTDIR.

    -r | --regex
        Specify date format for date extraction from filenames
        if there is no EXIF date information.

    -l | --log
        Redirect verbose output to named log file
        
        Example:
            {regex}
            can be used to extract the dafe from file names like
            the following IMG_27.01.2015-19.20.00.jpg.
""".format(version=version, regex="(?P<day>\d{2})\.(?P<month>\d{2})\.(?P<year>\d{4})[_-]?(?P<hour>\d{2})\.(?P<minute>\d{2})\.(?P<second>\d{2})"))


if __name__ == '__main__':
    main(sys.argv[1:])
