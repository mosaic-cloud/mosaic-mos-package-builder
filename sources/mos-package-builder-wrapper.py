#!/usr/bin/python2

if __name__ != "__main__" : raise Exception ("expected-main")

import os
import os.path as path
import sys
import urllib
import uuid

if os.environ.get ("JENKINS_URL") is not None and os.environ.get ("BUILD_TAG") is not None :
	_workbench = os.environ["WORKSPACE"]
	_temporary = path.join (os.environ.get ("TMPDIR", "/tmp"), "mosaic-mos-package-builder/temporary", os.environ["BUILD_TAG"])
else :
	_workbench = path.join (os.environ.get ("TMPDIR", "/tmp"), "mosaic-mos-package-builder/workbench")
	_temporary = path.join (os.environ.get ("TMPDIR", "/tmp"), "mosaic-mos-package-builder/temporary", uuid.uuid4 () .hex)

if not path.exists (_temporary) :
	os.makedirs (_temporary)

_script = "http://data.volution.ro/ciprian/public/mosaic/tools/mos-package-builder.py"

_configuration = {
		
		"descriptor" : None,
		"sources" : None,
		"package" : None,
		
		"package-name" : os.environ.get ("PackageName"),
		"package-version" : os.environ.get ("PackageVersion"),
		"package-release" : os.environ.get ("PackageRelease"),
		
		"workbench" : _workbench,
		"temporary" : _temporary,
		
		"execute" : True,
}

_script, _headers = urllib.urlretrieve (_script, path.join (_temporary, "builder.py"))
_script = open (_script)

_globals = {
		"__builtins__" : __builtins__,
		"__name__" : "__wrapped__",
		"__configuration__" : _configuration,
		"__exit__" : sys.exit,
}

exec (_script, _globals, _globals)

raise Exception ("expected-exit")
