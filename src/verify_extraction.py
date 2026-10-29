"""Private-original versus minimized-public-source verification through positional CSV decoding."""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
STATES={'ILLINOIS','INDIANA','MICHIGAN','MINNESOTA','OHIO','WISCONSIN'}
TYPES={'Flash Flood','Flood','Hail','Thunderstorm Wind','Tornado'}
FIELDS=['EPISODE_ID','EVENT_ID','STATE','YEAR','BEGIN_YEARMONTH','EVENT_TYPE','CZ_TYPE','WFO','DAMAGE_PROPERTY']


def main(originals):
    manifest=json.loads((ROOT/'data/source/manifest.json').read_text(encoding='utf-8'));assert manifest['status']=='COMPLETE'
    counts=[];fields_checked=0
    for record in manifest['files']:
        original=originals/record['source_filename']
        digest=hashlib.sha256()
        with original.open('rb') as f:
            for block in iter(lambda:f.read(1048576),b''):digest.update(block)
        assert digest.hexdigest()==record['original_sha256']
        public_blob=(ROOT/record['subset_file']).read_bytes();assert hashlib.sha256(public_blob).hexdigest()==record['subset_sha256']
        with gzip.open(ROOT/record['subset_file'],'rt',encoding='utf-8',newline='') as f:
            exported=list(csv.reader(f))
        assert exported.pop(0)==['source_row',*FIELDS]
        expected=[];total=0
        with gzip.open(original,'rt',encoding='latin-1',newline='') as f:
            source=csv.reader(f);header=next(source)
            indexes={key:next(i for i,label in enumerate(header) if label.removeprefix('\u00ef\u00bb\u00bf').upper()==key) for key in FIELDS}
            for row_number,row in enumerate(source,1):
                total=row_number
                if row[indexes['STATE']] in STATES and row[indexes['EVENT_TYPE']] in TYPES and row[indexes['CZ_TYPE']]=='C':
                    expected.append([str(row_number),*[row[indexes[k]] for k in FIELDS]])
        assert exported==expected and len(expected)==record['selected_rows'] and total==record['original_csv_rows']
        fields_checked+=len(expected)*len(FIELDS)
        counts.append({'year':record['year'],'selected_rows':len(expected),'original_rows':total,
                       'original_sha256':record['original_sha256'],'subset_sha256':record['subset_sha256']})
    report={'status':'PASS','checked_original_files':len(counts),'selected_original_fields_checked':fields_checked,
            'manifest_sha256':hashlib.sha256((ROOT/'data/source/manifest.json').read_bytes()).hexdigest(),
            'files':counts,'scope':'Every selected source string and source-row identifier compared against independently decoded private original files; entire original and minimized file hashes verified. Public CI replays only the minimized snapshot, not excluded originals.'}
    (ROOT/'results').mkdir(exist_ok=True)
    (ROOT/'results/ORIGINAL_EXTRACTION_CHECK.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['status','checked_original_files','selected_original_fields_checked']}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--private-source',type=Path,required=True)
    main(parser.parse_args().private_source)
