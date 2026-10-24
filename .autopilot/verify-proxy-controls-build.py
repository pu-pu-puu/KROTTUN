"""Read-only frozen archive verification. Never launches the executable."""
import ast
import hashlib
from pathlib import Path
import sys
import types
from PyInstaller.archive.readers import CArchiveReader

ROOT = Path(__file__).resolve().parents[1]

def fingerprint(code):
    def constant(value):
        if isinstance(value, types.CodeType):
            return fingerprint(value)
        if isinstance(value, tuple):
            return tuple(constant(item) for item in value)
        if isinstance(value, frozenset):
            return sorted((constant(item) for item in value), key=repr)
        return (type(value).__name__, repr(value))
    return (code.co_code, tuple(constant(item) for item in code.co_consts), code.co_names,
            code.co_varnames, code.co_freevars, code.co_cellvars, code.co_flags,
            code.co_argcount, code.co_posonlyargcount, code.co_kwonlyargcount)

def main():
    executable=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'dist/proxy-controls/KROTTUN.exe'
    archive=CArchiveReader(str(executable))
    verified=[]
    for relative in ('gui/web/index.html','bin/sing-box.exe','bin/wintun.dll'):
        key=next((name for name in archive.toc if name.replace('\\','/')==relative),None)
        assert key is not None, relative+' absent'
        assert archive.extract(key)==(ROOT/relative).read_bytes(), relative+' differs'
        verified.append(relative)
    pyz_key=next(name for name in archive.toc if name.endswith('PYZ.pyz'))
    pyz=archive.open_embedded_archive(pyz_key)
    for module in ('gui.app_webview','core.diagnostics','core.version','core.ping_service','core.proxy_model'):
        source=ROOT/(module.replace('.','/')+'.py')
        expected=compile(source.read_bytes(),str(source),'exec',optimize=0)
        assert fingerprint(pyz.extract(module))==fingerprint(expected), module+' bytecode differs'
        verified.append(module+' bytecode')
    expected=compile((ROOT/'main.py').read_bytes(),str(ROOT/'main.py'),'exec',optimize=0)
    import marshal
    assert fingerprint(marshal.loads(archive.extract('main')))==fingerprint(expected),'main bytecode differs'
    assert any('multiprocessing' in name for name in archive.toc),'multiprocessing hook absent'
    tree=ast.parse((ROOT/'core/version.py').read_text(encoding='utf-8-sig'))
    version=next(ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id=='APP_VERSION' for target in node.targets))
    print('PASS:',', '.join(verified),'; main; multiprocessing hook')
    print('Version:',version)
    print('Bytes:',executable.stat().st_size)
    print('SHA256:',hashlib.sha256(executable.read_bytes()).hexdigest())

if __name__=='__main__':
    main()
