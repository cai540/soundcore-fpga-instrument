"""Translate Windows absolute include names for Icarus's POSIX preprocessor.
Only include path spelling changes; the frozen synthesis input is never edited.
"""
from pathlib import Path
import hashlib,json,re

def iverilog_sources(files,output,root):
    output=Path(output);root=Path(root).resolve();output.mkdir(parents=True,exist_ok=True)
    translated=[];manifest=[]
    for index,source in enumerate(map(Path,files)):
        original=source.read_text(encoding='utf8')
        def include(match):
            name=match[1]
            if not re.match(r'^[A-Za-z]:[/\\]',name):return match[0]
            target=Path(name)
            if not target.is_file():raise FileNotFoundError(target)
            return '`include "'+target.resolve().relative_to(root).as_posix()+'"'
        body=re.sub(r'`include\s+"([^"]+)"',include,original)
        target=output/f'{index:03}_{source.name}'
        target.write_text(body,encoding='utf8')
        manifest.append(dict(source=str(source.resolve()),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                             simulation=str(target.resolve()),include_paths_only_changed=body!=original))
        translated.append(target)
    (output/'source_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    return translated
