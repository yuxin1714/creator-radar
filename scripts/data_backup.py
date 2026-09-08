"""Cross-platform PostgreSQL backup and isolated restore for the local workbench."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import uuid

ROOT=Path(__file__).resolve().parents[1]


def docker(*args, **kwargs):
    return subprocess.run(['docker','compose','exec','-T','postgres',*args],cwd=ROOT,check=True,stderr=subprocess.PIPE,**kwargs)


def identifier(value):
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,62}',value):raise ValueError('Invalid PostgreSQL identifier')
    return value


def database_settings():
    user=identifier(docker('printenv','POSTGRES_USER',stdout=subprocess.PIPE).stdout.decode().strip())
    database=identifier(docker('printenv','POSTGRES_DB',stdout=subprocess.PIPE).stdout.decode().strip())
    return user,database


def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def backup(output):
    user,database=database_settings()
    folder=output.resolve()/('backup-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8])
    folder.mkdir(parents=True,exist_ok=False)
    partial=folder/'database.dump.partial'
    with partial.open('xb') as stream:docker('pg_dump','-U',user,'-d',database,'-Fc','--no-owner','--no-privileges',stdout=stream)
    dump=folder/'database.dump';partial.rename(dump)
    revision=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
    manifest={'format':1,'created_at':datetime.now(timezone.utc).isoformat(),'git_revision':revision,'database':database,'sha256':digest(dump),'postgres_major':16,'includes':'database only; no API credentials, environment files, media cache or model weights'}
    with (folder/'manifest.json').open('x',encoding='utf-8') as stream:json.dump(manifest,stream,ensure_ascii=False,indent=2)
    print('Backup complete:',folder)
    return folder


def verify(folder):
    folder=folder.resolve()
    with (folder/'manifest.json').open(encoding='utf-8') as stream:manifest=json.load(stream)
    if manifest.get('format')!=1 or manifest.get('postgres_major')!=16:raise ValueError('Unsupported backup format')
    dump=folder/'database.dump'
    if digest(dump)!=manifest.get('sha256'):raise ValueError('Backup checksum mismatch; restore refused')
    print('Backup checksum verified')
    return dump


def restore(folder,target):
    if not re.fullmatch(r'creator_radar_restore_[a-z0-9_]{1,40}',target):
        raise ValueError('Restore target must start with creator_radar_restore_ and use lowercase letters, digits or underscores')
    user,database=database_settings()
    if target==database:raise ValueError('Cannot restore over the active application database')
    dump=verify(folder)
    # createdb refuses existing databases; never overwrite or drop user data.
    docker('createdb','-U',user,'--template=template0',target,stdout=subprocess.PIPE)
    with dump.open('rb') as stream:
        docker('pg_restore','-U',user,'--dbname='+target,'--no-owner','--no-privileges','--exit-on-error','--single-transaction',stdin=stream,stdout=subprocess.PIPE)
    print('Restored into isolated database:',target)
    print('The workbench database connection has not been changed.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    create=sub.add_parser('backup');create.add_argument('--output',type=Path,default=ROOT/'data'/'backups')
    check=sub.add_parser('verify');check.add_argument('folder',type=Path)
    recover=sub.add_parser('restore');recover.add_argument('folder',type=Path);recover.add_argument('--target',required=True)
    args=parser.parse_args()
    try:
        if args.command=='backup':backup(args.output)
        elif args.command=='verify':verify(args.folder)
        else:restore(args.folder,args.target)
    except (OSError,ValueError,subprocess.CalledProcessError) as error:
        if isinstance(error,subprocess.CalledProcessError):
            print('Database command failed; existing workbench data was not overwritten. Check Docker and database availability.')
        else:print(str(error))
        raise SystemExit(1)


if __name__=='__main__':main()
