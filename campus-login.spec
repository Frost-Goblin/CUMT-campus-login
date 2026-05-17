# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.building.datastruct import TOC


a = Analysis(
    ['E:\\campus-login\\desktop_app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('E:\\campus-login\\assets\\icons', 'assets\\icons'),
        ('E:\\campus-login\\assets\\fonts\\MiSansVF.subset.ttf', 'assets\\fonts'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PySide6.Qt3DAnimation',
        'PySide6.Qt3DCore',
        'PySide6.Qt3DExtras',
        'PySide6.Qt3DInput',
        'PySide6.Qt3DLogic',
        'PySide6.Qt3DRender',
        'PySide6.QtBluetooth',
        'PySide6.QtCharts',
        'PySide6.QtDataVisualization',
        'PySide6.QtDesigner',
        'PySide6.QtHelp',
        'PySide6.QtMultimedia',
        'PySide6.QtMultimediaWidgets',
        'PySide6.QtNetworkAuth',
        'PySide6.QtOpenGL',
        'PySide6.QtOpenGLWidgets',
        'PySide6.QtPdf',
        'PySide6.QtPdfWidgets',
        'PySide6.QtPositioning',
        'PySide6.QtPrintSupport',
        'PySide6.QtQml',
        'PySide6.QtQmlModels',
        'PySide6.QtQuick',
        'PySide6.QtQuickControls2',
        'PySide6.QtQuickWidgets',
        'PySide6.QtRemoteObjects',
        'PySide6.QtSensors',
        'PySide6.QtSerialPort',
        'PySide6.QtSql',
        'PySide6.QtStateMachine',
        'PySide6.QtTest',
        'PySide6.QtTextToSpeech',
        'PySide6.QtVirtualKeyboard',
        'PySide6.QtWebChannel',
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineQuick',
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebSockets',
        'PySide6.QtXml',
    ],
    noarchive=False,
    optimize=0,
)

EXCLUDED_BINARY_NAME_PREFIXES = (
    'qt6network',
    'qt6opengl',
    'qt6pdf',
    'qt6qml',
    'qt6quick',
    'qt6virtualkeyboard',
)
EXCLUDED_BINARY_NAMES = {
    'opengl32sw.dll',
    'qdirect2d.dll',
    'qgif.dll',
    'qico.dll',
    'qjpeg.dll',
    'qtga.dll',
    'qtiff.dll',
    'qwbmp.dll',
    'qwebp.dll',
    'qnetworkinformationbackend.dll',
    'qcertonlybackend.dll',
    'qopensslbackend.dll',
    'qschannelbackend.dll',
    'qnetwork.pyd',
    'qpdf.pyd',
    'qopengl.pyd',
    'qopenglwidgets.pyd',
    'qtopengl.pyd',
    'qtopenglwidgets.pyd',
    'qtpdf.pyd',
    'qtpdfwidgets.pyd',
    'qtqml.pyd',
    'qtqmlmodels.pyd',
    'qtquick.pyd',
    'qtquickcontrols2.pyd',
    'qtquickwidgets.pyd',
    'qtvirtualkeyboard.pyd',
}
EXCLUDED_BINARY_PATH_PARTS = (
    'plugins/imageformats/qgif',
    'plugins/imageformats/qico',
    'plugins/imageformats/qjpeg',
    'plugins/imageformats/qtga',
    'plugins/imageformats/qtiff',
    'plugins/imageformats/qwbmp',
    'plugins/imageformats/qwebp',
    'plugins/networkinformation/',
    'plugins/tls/',
    'platforminputcontexts/qtvirtualkeyboardplugin',
)


def keep_binary(entry):
    dest = entry[0].replace('\\', '/').lower()
    name = dest.rsplit('/', 1)[-1]
    if name in EXCLUDED_BINARY_NAMES:
        return False
    if any(name.startswith(prefix) for prefix in EXCLUDED_BINARY_NAME_PREFIXES):
        return False
    if any(part in dest for part in EXCLUDED_BINARY_PATH_PARTS):
        return False
    return True


a.binaries = TOC([entry for entry in a.binaries if keep_binary(entry)])
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='CUMT-Campus-Login',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon='E:\\campus-login\\assets\\icons\\app.ico',
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
