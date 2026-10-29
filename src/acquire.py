"""Retrieve once outside Git, then publish only the prespecified statistical fields."""
import argparse
import csv
from datetime import datetime,timezone
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import urllib.request
from config import ROOT,STATES,TYPES,FILES,FIELDS,BASE_URL


def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):
            digest.update(block)
    return digest.hexdigest()


def acquire(private_source):
    private_source=private_source.resolve()
    assert not private_source.is_relative_to(ROOT), 'Original narrative files must remain outside this Git checkout'
    private_source.mkdir(parents=True,exist_ok=True)
    out=ROOT/'data/source';out.mkdir(parents=True,exist_ok=True)
    manifest_path=out/'manifest.json'
    if manifest_path.exists():
        old=json.loads(manifest_path.read_text(encoding='utf-8'))
        assert old['status']=='COMPLETE', 'Preserve partial acquisition; investigate before resuming'
        for record in old['files']:
            assert sha(ROOT/record['subset_file'])==record['subset_sha256']
            assert sha(private_source/record['source_filename'])==record['original_sha256']
        print('Retained original and minimized source hashes verified; no network refresh')
        return
    manifest={'status':'ACQUIRING','started_utc':datetime.now(timezone.utc).isoformat(),
              'source':'NOAA NCEI / NWS Storm Events annual details',
              'public_fields':['source_row',*FIELDS],
              'encoding':'Latin-1 is a lossless byte-to-codepoint container decode; all retained field strings must be ASCII. Narratives and unused columns are discarded.',
              'row_index':'One-based parsed CSV data record number, not physical line number; quoted narratives can contain newlines.',
              'extraction_rule':'STATE in fixed six; EVENT_TYPE in fixed five; CZ_TYPE=C; exact selected source strings, no amount calculation',
              'originals':'Outside Git; source filename/hash retained without a private machine path',
              'files':[]}
    for year,creation in FILES.items():
        filename=f'StormEvents_details-ftp_v1.0_d{year}_c{creation}.csv.gz'
        target=private_source/filename
        assert not target.exists(), 'Do not silently reuse an unmanifested original download'
        url=BASE_URL+filename
        if os.name=='nt':
            subprocess.run(['powershell','-NoProfile','-File',str(ROOT/'src/download.ps1'),'-SourceUrl',url,'-TargetFile',str(target)],check=True,capture_output=True)
        else:
            with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Independent reproducible aggregate weather study'}),timeout=180) as response,target.open('wb') as f:
                while block:=response.read(1024*1024):f.write(block)
        selected=[];total=0
        with gzip.open(target,'rt',encoding='latin-1',newline='') as f:
            reader=csv.DictReader(f)
            names={name.removeprefix('\u00ef\u00bb\u00bf').upper():name for name in reader.fieldnames}
            assert all(field in names for field in FIELDS),reader.fieldnames
            header=list(reader.fieldnames)
            for index,row in enumerate(reader,1):
                total=index
                values={field:row[names[field]] for field in FIELDS}
                if values['STATE'] not in STATES or values['EVENT_TYPE'] not in TYPES or values['CZ_TYPE']!='C':continue
                assert int(values['YEAR'])==year
                assert all(value.isascii() for value in values.values())
                selected.append({'source_row':index,**values})
        text=io.StringIO(newline='')
        writer=csv.DictWriter(text,['source_row',*FIELDS],lineterminator='\n');writer.writeheader();writer.writerows(selected)
        name=f'data/source/selected-{year}.csv.gz'
        with (ROOT/name).open('wb') as raw,gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as zipped:
            zipped.write(text.getvalue().encode('utf-8'))
        record={'year':year,'source_filename':filename,'url':url,'retrieved_utc':datetime.now(timezone.utc).isoformat(),
                'original_sha256':sha(target),'original_bytes':target.stat().st_size,'original_csv_rows':total,
                'source_header':header,'subset_file':name,'subset_sha256':sha(ROOT/name),'selected_rows':len(selected)}
        manifest['files'].append(record)
        manifest_path.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'year':year,'source_rows':total,'selected_rows':len(selected),'original_bytes':target.stat().st_size}),flush=True)
    manifest['status']='COMPLETE';manifest['completed_utc']=datetime.now(timezone.utc).isoformat()
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--private-source',type=Path,required=True)
    acquire(parser.parse_args().private_source)
