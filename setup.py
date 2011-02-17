from fnmatch import filter as fnfilter
from sys import platform, argv
from os.path import join, dirname, realpath, sep, exists
from os import walk, environ
from distutils.core import setup
from distutils.extension import Extension

# extract version (simulate doc generation, kivy will be not imported)
environ['KIVY_DOC_INCLUDE'] = '1'
import kivy

# extra build commands go in the cmdclass dict {'command-name': CommandClass}
# see tools.packaging.{platform}.build.py for custom build commands for
# portable packages.  also e.g. we use build_ext command from cython if its
# installed for c extensions.
cmdclass = {}

# add build rules for portable packages to cmdclass
if platform == 'win32':
    from kivy.tools.packaging.win32.build import WindowsPortableBuild
    cmdclass['build_portable'] = WindowsPortableBuild
elif platform == 'darwin':
    from kivy.tools.packaging.osx.build import OSXPortableBuild
    cmdclass['build_portable'] = OSXPortableBuild

from kivy.tools.packaging.factory import FactoryBuild
cmdclass['build_factory'] = FactoryBuild

#
# Detect options
#
c_options = {
    'use_opengl_es2': True,
    'use_opengl_debug': False,
    'use_glew': False,
    'use_mesagl': False}

# Detect which opengl version headers to use
if platform == 'win32':
    print 'Windows platform detected, force GLEW usage.'
    c_options['use_glew'] = True
elif platform == 'darwin':
    # macosx is using their own gl.h
    pass
else:
    # searching GLES headers
    default_header_dirs = ['/usr/include', '/usr/local/include']
    found = False
    for hdir in default_header_dirs:
        filename = join(hdir, 'GLES2', 'gl2.h')
        if exists(filename):
            found = True
            print 'Found GLES 2.0 headers at', filename
            break
    if not found:
        print 'WARNING: GLES 2.0 headers are not found'
        print 'Fallback to Desktop opengl headers.'
        c_options['use_opengl_es2'] = False

print 'Generate config.h'
with open(join(dirname(__file__), 'kivy', 'graphics', 'config.h'), 'w') as fd:
    fd.write('// Autogenerated file for Kivy C configuration\n')
    for k, v in c_options.iteritems():
        fd.write('#define __%s %d\n' % (k.upper(), int(v)))

print 'Generate config.pxi'
with open(join(dirname(__file__), 'kivy', 'graphics', 'config.pxi'), 'w') as fd:
    fd.write('# Autogenerated file for Kivy Cython configuration\n')
    for k, v in c_options.iteritems():
        fd.write('DEF %s = %d\n' % (k.upper(), int(v)))

# extension modules
ext_modules = []

# list all files to compile
pyx_files = []
kivy_libs_dir = realpath(kivy.kivy_libs_dir)
for root, dirnames, filenames in walk(join(dirname(__file__), 'kivy')):
    # ignore lib directory
    if realpath(root).startswith(kivy_libs_dir):
        continue
    for filename in fnfilter(filenames, '*.pyx'):
        pyx_files.append(join(root, filename))

# check for cython
try:
    have_cython = True
    from Cython.Distutils import build_ext
except:
    have_cython = False

# create .c for every module
if 'sdist' in argv and have_cython:
    from Cython.Compiler.Main import compile
    print 'Generating C files...',
    compile(pyx_files)
    print 'Done !'

# add cython core extension modules if cython is available
if have_cython:
    cmdclass['build_ext'] = build_ext
else:
    pyx_files = ['%s.c' % x[:-4] for x in pyx_files]

if True:
    libraries = []
    include_dirs = []
    extra_link_args = []
    if platform == 'win32':
        libraries.append('opengl32')
    elif platform == 'darwin':
        # On OSX, it's not -lGL, but -framework OpenGL...
        extra_link_args = ['-framework', 'OpenGL']
    elif platform.startswith('freebsd'):
        include_dirs += ['/usr/local/include']
        extra_link_args += ['-L', '/usr/local/lib']
    else:
        libraries.append('GLESv2')

    if c_options['use_glew']:
        if platform == 'win32':
            libraries.append('glew32')
        else:
            libraries.append('GLEW')

    def get_modulename_from_file(filename):
        pyx = '.'.join(filename.split('.')[:-1])
        pyxl = pyx.split(sep)
        while pyxl[0] != 'kivy':
            pyxl.pop(0)
        if pyxl[1] == 'kivy':
            pyxl.pop(0)
        return '.'.join(pyxl)

    OrigExtension = Extension

    def Extension(*args, **kwargs):
        # Small hack to only compile for x86_64 on OSX.
        # Is there a better way to do this?
        if platform == 'darwin':
            extra_args = ['-arch', 'x86_64']
            kwargs['extra_compile_args'] = extra_args + \
                kwargs.get('extra_compile_args', [])
            kwargs['extra_link_args'] = extra_args + \
                kwargs.get('extra_link_args', [])
        return OrigExtension(*args, **kwargs)

    # simple extensions
    for pyx in (x for x in pyx_files if not 'graphics' in x):
        module_name = get_modulename_from_file(pyx)
        ext_modules.append(Extension(module_name, [pyx]))

    # opengl aware modules
    for pyx in (x for x in pyx_files if 'graphics' in x):
        module_name = get_modulename_from_file(pyx)
        ext_modules.append(Extension(
            module_name, [pyx],
            libraries=libraries,
            include_dirs=include_dirs,
            extra_link_args=extra_link_args))


    #poly2try extension
    """
    ext_modules.append(Extension('kivy.c_ext.p2t', [
     'kivy/lib/poly2tri/src/p2t.pyx',
     'kivy/lib/poly2tri/poly2tri/common/shapes.cc',
     'kivy/lib/poly2tri/poly2tri/sweep/advancing_front.cc',
     'kivy/lib/poly2tri/poly2tri/sweep/cdt.cc',
     'kivy/lib/poly2tri/poly2tri/sweep/sweep.cc',
     'kivy/lib/poly2tri/poly2tri/sweep/sweep_context.cc'
    ], language="c++"))
    """

#setup datafiles to be included in the disytibution, liek examples...
#extracts all examples files except sandbox
data_file_prefix = 'share/kivy-'
examples = {}
examples_allowed_ext = ('readme', 'py', 'wav', 'png', 'jpg', 'svg',
                        'avi', 'gif', 'txt', 'ttf', 'obj', 'mtl', 'kv')
for root, subFolders, files in walk('examples'):
    if 'sandbox' in root:
        continue
    for file in files:
        ext = file.split('.')[-1].lower()
        if ext not in examples_allowed_ext:
            continue
        filename = join(root, file)
        directory = '%s%s' % (data_file_prefix, dirname(filename))
        if not directory in examples:
            examples[directory] = []
        examples[directory].append(filename)



# setup !
setup(
    name='Kivy',
    version=kivy.__version__,
    author='Kivy Crew',
    author_email='kivy-dev@googlegroups.com',
    url='http://kivy.org/',
    license='LGPL',
    description='A software library for rapid development of ' + \
                'hardware-accelerated multitouch applications.',
    ext_modules=ext_modules,
    cmdclass=cmdclass,
    packages=[
        'kivy',
        'kivy.core',
        'kivy.core.audio',
        'kivy.core.camera',
        'kivy.core.clipboard',
        'kivy.core.image',
        'kivy.core.gl',
        'kivy.core.spelling',
        'kivy.core.svg',
        'kivy.core.text',
        'kivy.core.video',
        'kivy.core.window',
        'kivy.graphics',
        'kivy.input',
        'kivy.input.postproc',
        'kivy.input.providers',
        'kivy.lib',
        'kivy.lib.osc',
        'kivy.modules',
        'kivy.tools',
        'kivy.tools.packaging',
        'kivy.tools.packaging.win32',
        'kivy.tools.packaging.osx',
        'kivy.uix',
    ],
    package_dir={'kivy': 'kivy'},
    package_data={'kivy': [
        'data/*.kv',
        'data/fonts/*.ttf',
        'data/images/*.png',
        'data/logo/*.png',
        'data/glsl/*.png',
        'data/glsl/*.vs',
        'data/glsl/*.fs',
        'tools/packaging/README.txt',
        'tools/packaging/win32/kivy.bat',
        'tools/packaging/win32/kivyenv.sh',
        'tools/packaging/win32/README.txt',
        'tools/packaging/osx/kivy.sh']},
    data_files=examples.items(),
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: MacOS X',
        'Environment :: Win32 (MS Windows)',
        'Environment :: X11 Applications',
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Desktop',
        'Intended Audience :: Information Technology',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: GNU Library or Lesser '
        'General Public License (LGPL)',
        'Natural Language :: English',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: POSIX :: BSD :: FreeBSD',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Topic :: Artistic Software',
        'Topic :: Games/Entertainment',
        'Topic :: Multimedia :: Graphics :: 3D Rendering',
        'Topic :: Multimedia :: Graphics :: Capture :: Digital Camera',
        'Topic :: Multimedia :: Graphics :: Presentation',
        'Topic :: Multimedia :: Graphics :: Viewers',
        'Topic :: Multimedia :: Sound/Audio :: Players :: MP3',
        'Topic :: Multimedia :: Video :: Display',
        'Topic :: Scientific/Engineering :: Human Machine Interfaces',
        'Topic :: Scientific/Engineering :: Visualization',
        'Topic :: Software Development :: Libraries :: Application Frameworks',
        'Topic :: Software Development :: User Interfaces'])

