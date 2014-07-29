#!/usr/bin/python2

if __name__ != "__main__" : raise Exception ("expected-main")

import os
import sys
import urllib

_script = "http://data.volution.ro/ciprian/public/mosaic/tools/mos-package-builder.py"
_workbench = os.environ["WORKSPACE"]
_sources = "%s/sources.zip" % (_workbench,)
_package = "%s/package.rpm" % (_workbench,)
_temporary = "/tmp/mosaic-mos-package-builder/temporary/%s" % (os.environ["BUILD_TAG"],)

_configuration = {
		
		"descriptor" : None,
		"sources" : _sources,
		"package" : _package,
		"temporary" : _temporary,
		
		"package-name" : os.environ.get ("PackageName"),
		"package-version" : os.environ.get ("PackageVersion"),
		"package-release" : os.environ.get ("PackageRelease"),
		"package-distribution" : os.environ.get ("PackageDistribution"),
}

_script, _headers = urllib.urlretrieve (_script, "./builder.py")
_script = open (_script)

_globals = {
		"__builtins__" : __builtins__,
		"__name__" : "__wrapped__",
		"__configuration__" : _configuration,
		"__exit__" : sys.exit,
}

exec (_script, _globals, _globals)

raise Exception ("expected-exit")
