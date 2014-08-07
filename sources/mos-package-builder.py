#!/usr/bin/python2


import json
import re
import os
import os.path as path
import subprocess
import sys
import time
import uuid


def _main (_configuration) :
	
	_descriptor = _configuration["descriptor"]
	_sources = _configuration["sources"]
	_package_archive = _configuration["package"]
	_workbench = _configuration["workbench"]
	_temporary = _configuration["temporary"]
	
	_package_name = _configuration["package-name"]
	_package_version = _configuration["package-version"]
	_package_release = _configuration["package-release"]
	_package_distribution = _configuration["package-distribution"]
	
	_execute = _configuration["execute"]
	
	if _temporary is None :
		_logger.info ("unspecified temporary; using a random one!")
		_temporary = path.realpath (path.join (path.join (os.environ.get ("TMPDIR", "/tmp"), "mosaic-mos-package-builder/temporary", uuid.uuid4 () .hex)))
		MkdirCommand () .execute (_temporary, True)
	
	if _sources is None :
		if _workbench is not None :
			for _sources_name in ["sources", "sources.zip", "sources.tar", "sources.cpio"] :
				if path.exists (path.join (_workbench, _sources_name)) :
					_sources = path.join (_workbench, _sources_name)
					break
	
	if _sources is None :
		_logger.info ("unspecified sources; ignoring!")
		_sources_root = None
		_sources_archive = None
	elif path.isdir (_sources) :
		_sources_root = path.realpath (_sources)
		_sources_archive = None
	elif path.isfile (_sources) or path.exists (_sources) :
		# FIXME: Check if the path is a regular file or a fifo (not something else)!
		_logger.debug ("extracting sources archive...")
		_sources_archive = _sources
		_sources_root = path.realpath (path.join (_temporary, "sources"))
		if _sources_archive.endswith (".zip") :
			SafeZipExtractCommand () .execute (_sources_root, _sources_archive)
		elif _sources_archive.endswith (".tar") :
			SafeTarExtractCommand () .execute (_sources_root, _sources_archive)
		elif _sources_archive.endswith (".cpio") :
			SafeCpioExtractCommand () .execute (_sources_root, _sources_archive)
		else :
			raise _error ("wtf!")
	else :
		raise _error ("wtf!")
	
	if _descriptor is None :
		if _workbench is not None :
			if path.exists (path.join (_workbench, "package.json")) :
				_descriptor = path.join (_workbench, "package.json")
	
	if _descriptor is None :
		_logger.info ("unspecified descriptor; using `package.json`!")
		if _sources_root is None :
			raise _error ("wtf!")
		_descriptor = path.join (_sources_root, "package.json")
	_descriptor = path.realpath (_descriptor)
	
	if _package_archive is None :
		if _workbench is not None :
			_package_archive = path.join (_workbench, "package.rpm")
	
	if _package_archive is None :
		_logger.info ("unspecified package archive; using `package.rpm`!")
		_package_archive = path.realpath (path.join (_temporary, "package.rpm"))
	else :
		_package_archive = path.realpath (_package_archive)
	
	_package_scratch = path.realpath (path.join (_temporary, "package"))
	
	_logger.info ("arguments:")
	_logger.info ("  -> descriptor: `%s`;", _descriptor)
	_logger.info ("  -> sources archive: `%s`;", _sources_archive)
	_logger.info ("  -> sources root: `%s`;", _sources_root)
	_logger.info ("  -> package archive: `%s`;", _package_archive)
	_logger.info ("  -> package scratch: `%s`;", _package_scratch)
	_logger.info ("  -> temporary: `%s`;", _temporary)
	_logger.info ("  -> package name: `%s`;", _package_name)
	_logger.info ("  -> package version: `%s`;", _package_version)
	_logger.info ("  -> package release: `%s`;", _package_release)
	_logger.info ("  -> package distribution: `%s`;", _package_distribution)
	
	os.chdir (_temporary)
	os.environ["TMPDIR"] = _temporary
	
	
	if os.path.exists (_package_archive) :
		_logger.warn ("existing package archive; deleting!")
		RmCommand () .execute (_package_archive)
	
	_definitions = {}
	if _package_name is not None :
		_definitions["package:name"] = _package_name
	if _package_version is not None :
		_definitions["distribution:version"] = _package_version
	if _package_release is not None :
		_definitions["distribution:release"] = _package_release
	if _package_distribution is not None :
		_definitions["distribution:label"] = _package_distribution
	
	_logger.info ("initializing builder...")
	_builder = _create_builder (
			descriptor = _json_load (_descriptor),
			sources = _sources_root,
			package_archive = _package_archive,
			package_outputs = _package_scratch,
			temporary = _temporary,
			definitions = _definitions,
	)
	
	_logger.info ("generating commands...")
	_prepare = _builder.instantiate ("prepare")
	_assemble = _builder.instantiate ("assemble")
	_package = _builder.instantiate ("package")
	_cleanup = _builder.instantiate ("cleanup")
	
	if True :
		_scroll = Scroll ()
		
		_builder.describe (_scroll)
		
		_scroll.stream (lambda _line : _logger.debug ("%s", _line))
	
	if True :
		_scroll = Scroll ()
		
		_scroll.append ("prepare commands:")
		_prepare.describe (_scroll.splice (indentation = 1))
		
		_scroll.append ("assemble commands:")
		_assemble.describe (_scroll.splice (indentation = 1))
		
		_scroll.append ("package commands:")
		_package.describe (_scroll.splice (indentation = 1))
		
		_scroll.append ("cleanup commands:")
		_cleanup.describe (_scroll.splice (indentation = 1))
		
		_scroll.stream (lambda _line : _logger.debug ("%s", _line))
	
	if False :
		_scroll = Scroll ()
		
		_scroll.append ("rpm specification:")
		_scroll.include_scroll (_builder._generate_rpm_spec (), indentation = 1)
		
		_scroll.stream (lambda _line : _logger.debug ("%s", _line))
	
	if _execute :
		
		_logger.info ("executing prepare commands...")
		_prepare.execute ()
		
		_logger.info ("executing assemble commands...")
		_assemble.execute ()
		
		_logger.info ("executing package commands...")
		_package.execute ()
		
		_logger.info ("executing cleanup commands...")
		_cleanup.execute ()
		
		_logger.info ("succeeded; package available at `%s`!", _package_archive)


class Builder (object) :
	
	def __init__ (self, _temporary, _definitions) :
		
		self._context = Context ()
		self._definitions_ = _definitions
		if self._definitions_ is None :
			self._definitions_ = {}
		
		self._temporary = PathValue (self._context, [_temporary], identifier = "execution:temporary")
		self._resource_outputs = PathValue (self._context, [self._temporary, "resources"], identifier = "execution:resources:outputs")
		self._timestamp = ConstantValue (self._context, int (time.time ()), identifier = "execution:timestamp")
		
		self._definitions = {}
		self._resources = {}
		self._overlays = []
		
		self._command_environment = {
				"TMPDIR" : self._temporary,
		}
		self._command_arguments = {
				"environment" : self._command_environment,
		}
	
	def _initialize_definitions (self, _descriptors_) :
		
		_descriptors = {}
		_descriptors.update (_descriptors_)
		_descriptors.update (self._definitions_)
		self._definitions = {}
		for _identifier in _descriptors :
			self._initialize_definition (_identifier, _json_select (_descriptors, (_identifier,), basestring))
	
	def _initialize_definition (self, _identifier, _template) :
		if _identifier in self._definitions :
			raise _error ("d6e8010c")
		_definition = ExpandableStringValue (self._context, _template, identifier = "definitions:%s" % (_identifier,))
		self._definitions[_identifier] = _definition
	
	def _initialize_resources (self, _descriptors) :
		for _identifier in _descriptors :
			_descriptor = _json_select (_descriptors, (_identifier,), dict)
			self._initialize_resource (_identifier, _descriptor)
	
	def _initialize_resource (self, _identifier, _descriptor) :
		
		if _identifier in self._resources :
			raise _error ("f5607669")
		
		_generator = _json_select (_descriptor, ("generator",), basestring)
		
		if _generator == "fetcher" :
			_uri = ExpandableStringValue (self._context, _json_select (_descriptor, ("uri",), basestring), pattern = _resource_uri_re)
			_target = PathValue (self._context, [_identifier], pattern = _target_path_re)
			_resource = FetcherResource (self, _identifier, _uri, self._resource_outputs, _target)
			
		elif _generator == "sources" :
			_source = PathValue (self._context, [ExpandableStringValue (self._context, _json_select (_descriptor, ("path",), basestring))], pattern = _target_path_re)
			_target = PathValue (self._context, [_identifier], pattern = _target_path_re)
			_resource = ClonedResource (self, _identifier, self._sources, _source, self._resource_outputs, _target)
			
		else :
			raise _error ("cf3a6b47", identifier = _identifier, descriptor = _descriptor)
		
		self._resources[_identifier] = _resource
	
	def _initialize_overlays (self, _descriptors, _root) :
		for _index in xrange (len (_descriptors)) :
			self._initialize_overlay (_index, _json_select (_descriptors, (_index,), dict), _root)
	
	def _initialize_overlay (self, _index, _descriptor, _root) :
		
		_target = PathValue (self._context, [ExpandableStringValue (self._context, _json_select (_descriptor, ("target",), basestring))], pattern = _target_path_re)
		_generator = _json_select (_descriptor, ("generator",), basestring)
		
		if _generator == "unarchiver" :
			_resource = ResolvableValue (self._context, ExpandableStringValue (self._context, _json_select (_descriptor, ("resource",), basestring), pattern = _context_value_identifier_re), self.resolve_resource)
			_format = ExpandableStringValue (self._context, _json_select (_descriptor, ("format",), basestring))
			_options = _json_select (_descriptor, ("options",), dict, required = False, default = {})
			_overlay = UnarchiverOverlay (self, _root, _target, lambda : _resource () .path, _format, _options)
			
		elif _generator == "file-creator" :
			_resource = ResolvableValue (self._context, ExpandableStringValue (self._context, _json_select (_descriptor, ("resource",), basestring), pattern = _context_value_identifier_re), self.resolve_resource)
			_executable = _json_select (_descriptor, ("executable",), bool, required = False, default = False)
			_expand = _json_select (_descriptor, ("expand",), bool, required = False, default = False)
			_overlay = FileCreatorOverlay (self, _root, _target, _resource () .path, _executable, _expand, self._context.resolve_value)
			
		elif _generator == "symlinks" :
			_links = []
			for _link_target in _json_select (_descriptor, ("links",), dict) :
				_link_source = _json_select (_descriptor, ("links", _link_target,), basestring)
				_link_target = PathValue (self._context, [ExpandableStringValue (self._context, _link_target)], pattern = _target_path_re)
				_link_source = PathValue (self._context, [ExpandableStringValue (self._context, _link_source)], pattern = _normal_path_re)
				_links.append ((_link_target, _link_source))
			_overlay = SymlinksOverlay (self, _root, _target, _links)
			
		elif _generator == "renames" :
			_renames = []
			for _rename_target in _json_select (_descriptor, ("renames",), dict) :
				_rename_source = _json_select (_descriptor, ("renames", _rename_target,), basestring)
				_rename_target = PathValue (self._context, [ExpandableStringValue (self._context, _rename_target)], pattern = _target_path_re)
				_rename_source = PathValue (self._context, [ExpandableStringValue (self._context, _rename_source)], pattern = _target_path_re)
				_renames.append ((_rename_target, _rename_source))
			_overlay = RenamesOverlay (self, _root, _target, _renames)
			
		elif _generator == "folders" :
			_folders = []
			for _folder_target in _json_select (_descriptor, ("folders",), list) :
				_folder_target = PathValue (self._context, [ExpandableStringValue (self._context, _folder_target)], pattern = _target_path_re)
				_folders.append (_folder_target)
			_overlay = FoldersOverlay (self, _root, _target, _folders)
			
		else :
			raise _error ("93fe5c5d", descriptor = _descriptor)
		
		self._overlays.append (_overlay)
	
	def instantiate (self, _phase) :
		raise _error ("300e7568")
	
	def describe (self, _scroll) :
		raise _error ("c947398f")
	
	def _describe_definitions (self, _scroll) :
		_scroll.append ("definitions:")
		_subscroll = _scroll.splice (indentation = 1)
		if self._definitions is not None :
			for _identifier in sorted (self._definitions.keys ()) :
				_value = self._definitions[_identifier]
				if _identifier in self._definitions_ :
					_subscroll.appendf ("`%s`: `%s` (overriden);", _identifier, _value)
				else :
					_subscroll.appendf ("`%s`: `%s`;", _identifier, _value)
	
	def _describe_resources (self, _scroll) :
		_scroll.append ("resources:")
		_subscroll = _scroll.splice (indentation = 1)
		for _resource_identifier in sorted (self._resources.keys ()) :
			_resource = self._resources[_resource_identifier]
			_resource.describe (_subscroll)
	
	def _describe_overlays (self, _scroll) :
		_scroll.append ("overlays:")
		_subscroll = _scroll.splice (indentation = 1)
		for _overlay in self._overlays :
			_overlay.describe (_subscroll)
	
	def resolve_resource (self, _identifier) :
		if _identifier not in self._resources :
			raise _error ("c929637c", identifier = _identifier)
		return self._resources[_identifier]


def _create_builder (descriptor = None, **_arguments) :
	
	_schema = _json_select (descriptor, ("_schema",), basestring)
	_schema_version = _json_select (descriptor, ("_schema/version",), int)
	
	if _schema == "tag:ieat.ro,2014:mosaic:v2:mos-package-builder:descriptors:composite-package" and _schema_version == 1 :
		_builder = CompositePackageBuilder (descriptor = descriptor, **_arguments)
		
	else :
		raise _error ("7882db14")
	
	return _builder


class CompositePackageBuilder (Builder) :
	
	def __init__ (self, descriptor = None, sources = None, package_archive = None, package_outputs = None, temporary = None, definitions = None) :
		
		Builder.__init__ (self, temporary, definitions)
		
		if sources is not None :
			self._sources = PathValue (self, [sources])
		else :
			self._sources = None
		
		self._package_archive = PathValue (self, [package_archive])
		self._package_outputs = PathValue (self, [package_outputs])
		
		self._initialize (descriptor)
	
	def instantiate (self, _phase) :
		if _phase == "prepare" :
			return self._instantiate_prepare ()
		elif _phase == "assemble" :
			return self._instantiate_assemble ()
		elif _phase == "package" :
			return self._instantiate_package ()
		elif _phase == "cleanup" :
			return self._instantiate_cleanup ()
		else :
			raise _error ("c0072485")
	
	def _instantiate_prepare (self) :
		_commands = []
		_commands.append (MkdirCommand (**self._command_arguments) .instantiate (self._resource_outputs))
		for _resource in self._resources.values () :
			_commands.append (_resource.instantiate ())
		return SequentialCommandInstance (_commands)
	
	def _instantiate_assemble (self) :
		_commands = []
		_commands.append (MkdirCommand (**self._command_arguments) .instantiate (self._package_outputs))
		for _overlay in self._overlays :
			_commands.append (_overlay.instantiate ())
		return SequentialCommandInstance (_commands)
	
	def _instantiate_package (self) :
		_commands = []
		_commands.append (SafeFileCreateCommand (**self._command_arguments) .instantiate (self.rpm_spec, LambdaValue (self._context, lambda : self._generate_rpm_spec () .lines_with_nl ())))
		_commands.append (self._generate_rpm_command ())
		return SequentialCommandInstance (_commands)
	
	def _instantiate_cleanup (self) :
		_commands = []
		_commands.append (ChmodCommand (**self._command_arguments) .instantiate (self._temporary, "u=rxw", True))
		_commands.append (RmCommand (**self._command_arguments) .instantiate (self._temporary, True))
		return SequentialCommandInstance (_commands)
	
	def _generate_rpm_spec (self) :
		
		_scroll = Scroll ()
		_scroll.append ("")
		
		_scroll.appendf ("name: %s", self.package_name)
		_scroll.appendf ("version: %s", self.package_version)
		_scroll.appendf ("release: %s", self.package_release)
		_scroll.appendf ("exclusivearch: %s", self.package_architecture)
		_scroll.append ("")
		# epoch
		# excludearch
		# exclusivearch
		# excludeos
		# exclusiveos
		
		_scroll.appendf ("prefix: %s", self.package_root)
		_scroll.append ("")
		
		_scroll.appendf ("buildarch: %s", self.package_architecture)
		_scroll.appendf ("buildroot: %s", self._package_outputs)
		_scroll.append ("")
		# buildrequires
		# buildconflicts
		# buildprereq
		
		# source, nosource
		# patch, nopatch
		
		_scroll.appendf ("url: %s", self.rpm_url)
		_scroll.appendf ("license: %s", self.rpm_license)
		_scroll.appendf ("summary: %s", self.rpm_summary)
		_scroll.append ("")
		# distribution
		# group
		# vendor
		# packager
		
		if len (self._rpm_provides) > 0 :
			for _rpm_provides in self._rpm_provides :
				_scroll.appendf ("provides: %s", _rpm_provides)
			_scroll.append ("")
		
		if len (self._rpm_requires) > 0 :
			for _rpm_requires in self._rpm_requires :
				_scroll.appendf ("requires: %s", _rpm_requires)
			_scroll.append ("")
		
		# conflicts
		# obsoletes
		
		_scroll.append ("autoprov: no")
		_scroll.append ("autoreq: no")
		_scroll.append ("")
		
		_scroll.append ("%description")
		_scroll.appendf ("%s", self.rpm_summary, indentation = 1)
		_scroll.append ("")
		
		_scroll.append ("%prep")
		_scroll.append ("true", indentation = 1)
		_scroll.append ("%build")
		_scroll.append ("true", indentation = 1)
		_scroll.append ("%install")
		_scroll.append ("true", indentation = 1)
		_scroll.append ("%check")
		_scroll.append ("true", indentation = 1)
		_scroll.append ("%clean")
		_scroll.append ("true", indentation = 1)
		_scroll.append ("")
		
		_scroll.append ("%files")
		_scroll.append ("%defattr(-,root,root,-)", indentation = 1)
		_scroll.appendf ("%s", self.package_root, indentation = 1)
		_scroll.append ("")
		
		# pre
		# post
		# preun
		# postun
		# verifyscript
		
		return _scroll
	
	def _generate_rpm_command (self) :
		_commands = []
		
		_true_path = _resolve_executable_path ("true")
		
		_commands.append (MkdirCommand (**self._command_arguments) .instantiate (self.rpm_outputs))
		
		_commands.append (RpmBuildCommand (setarch = self.package_architecture, **self._command_arguments) .instantiate (self.rpm_spec,
				
				rpm_macros = "/dev/null",
				rpm_buildroot = self._package_outputs,
				
				rpm_defines = {
						
						"_topdir" : self.rpm_outputs,
						
						"_specdir" : "%{_topdir}/SPECS",
						"_sourcedir" : "%{_topdir}/SOURCES",
						"_rpmdir" : "%{_topdir}/RPMS",
						"_srcrpmdir" : "%{_topdir}/SRPMS",
						"_builddir" : "%{_topdir}/BUILD",
						"_buildrootdir" : "%{_topdir}/BUILDROOT",
						
						"_tmppath" : self._temporary,
						
						"_rpmfilename" : "package.rpm",
						
						"__find_provides" : _true_path,
						"__find_requires" : _true_path,
						"__find_conflicts" : _true_path,
						"__find_obsoletes" : _true_path,
						
						"__check_files" : _true_path,
						
						"__spec_prep_cmd" : _true_path,
						"__spec_build_cmd" : _true_path,
						"__spec_install_cmd" : _true_path,
						"__spec_check_cmd" : _true_path,
						"__spec_clean_cmd" : _true_path,
				},
				
				# rpm_rc = "/dev/null",
				rpm_db = PathValue (None, [self.rpm_outputs, "DB"]),
		))
		
		_commands.append (CpCommand (**self._command_arguments) .instantiate (
				self._package_archive,
				PathValue (self._context, [self.rpm_outputs, "RPMS/package.rpm"])))
		
		return SequentialCommandInstance (_commands)
	
	def _initialize (self, _descriptor) :
		self._initialize_package (_descriptor)
		self._initialize_definitions (_json_select (_descriptor, ("definitions",), dict, required = False, default = {}))
		self._initialize_resources (_json_select (_descriptor, ("resources",), dict, required = False, default = {}))
		self._initialize_overlays (_json_select (_descriptor, ("overlays",), list, required = False, default = []), self._package_outputs)
		self._initialize_dependencies (_json_select (_descriptor, ("dependencies",), dict, required = False, default = {}))
		self._initialize_rpm (_descriptor)
	
	def _initialize_package (self, _descriptor) :
		
		self.package_name = ExpandableStringValue (self._context,
				_json_select (_descriptor, ("package", "name"), basestring),
				pattern = _rpm_package_name_re, identifier = "package:name")
		self.package_version = ExpandableStringValue (self._context,
				_json_select (_descriptor, ("package", "version"), basestring),
				pattern = _rpm_package_version_re, identifier = "package:version")
		self.package_release = ExpandableStringValue (self._context,
				_json_select (_descriptor, ("package", "release"), basestring),
				pattern = _rpm_package_release_re, identifier = "package:release")
		self.package_architecture = ExpandableStringValue (self._context,
				_json_select (_descriptor, ("package", "architecture"), basestring),
				pattern = _rpm_architecture_re, identifier = "package:architecture")
		self.package_root = PathValue (self._context,
				[ExpandableStringValue (self._context,
						_json_select (_descriptor, ("package", "root"), basestring),
						pattern = _target_path_re)],
				identifier = "package:root")
		self.package_identifier = LambdaValue (self._context,
				lambda : "%s-%s" % (self.package_name (), self.package_version ()),
				identifier = "package:identifier")
	
	def _initialize_rpm (self, _descriptor) :
		
		self.rpm_license = LicenseValue (self._context,
				ExpandableStringValue (self._context,
						_json_select (_descriptor, ("miscellaneous", "license"), basestring, required = False)))
		self.rpm_summary = ExpandableStringValue (self._context,
				_json_select (_descriptor, ("miscellaneous", "summary"), basestring, required = False))
		self.rpm_url = ExpandableStringValue (self._context,
				_json_select (_descriptor, ("miscellaneous", "url"), basestring, required = False))
		
		self.rpm_outputs = PathValue (self._context, [self._temporary, "rpm-outputs"])
		self.rpm_spec = PathValue (self._context, [self._temporary, "rpm.spec"])
	
	def _initialize_dependencies (self, _descriptor) :
		self._initialize_provides (_json_select (_descriptor, ("provides",), list, required = False, default = []))
		self._initialize_requires (_json_select (_descriptor, ("requires",), list, required = False, default = []))
	
	def _initialize_provides (self, _descriptors) :
		self._rpm_provides = []
		for _index in xrange (len (_descriptors)) :
			_provided = ExpandableStringValue (self._context,
					_json_select (_descriptors, (_index,), basestring),
					pattern = _rpm_package_name_re)
			self._rpm_provides.append (_provided)
	
	def _initialize_requires (self, _descriptors) :
		self._rpm_requires = []
		for _index in xrange (len (_descriptors)) :
			_required = ExpandableStringValue (self._context,
					_json_select (_descriptors, (_index,), basestring),
					pattern = _rpm_package_name_re)
			self._rpm_requires.append (_required)
	
	def describe (self, _scroll) :
		
		_scroll.append ("composite package builder:")
		
		_scroll.append ("package:", indentation = 1)
		_subscroll = _scroll.splice (indentation = 2)
		_subscroll.appendf ("name: `%s`;", self.package_name)
		_subscroll.appendf ("version: `%s`;", self.package_version)
		_subscroll.appendf ("release: `%s`;", self.package_release)
		_subscroll.appendf ("architecture: `%s;`", self.package_architecture)
		_subscroll.appendf ("root: `%s;`", self.package_root)
		
		_scroll.append ("provides:", indentation = 2)
		_subscroll = _scroll.splice (indentation = 3)
		for _provided in self._rpm_provides :
			_subscroll.appendf ("`%s`;", _provided)
		
		_scroll.append ("requires:", indentation = 2)
		_subscroll = _scroll.splice (indentation = 3)
		for _required in self._rpm_requires :
			_subscroll.appendf ("`%s`;", _required)
		
		_subscroll = _scroll.splice (indentation = 1)
		self._describe_resources (_subscroll)
		self._describe_overlays (_subscroll)
		
		_scroll.append ("environment:", indentation = 1)
		_subscroll = _scroll.splice (indentation = 2)
		_subscroll.appendf ("sources: `%s`;", self._sources)
		_subscroll.appendf ("package archive: `%s`;", self._package_archive)
		_subscroll.appendf ("package outputs: `%s`;", self._package_outputs)
		_subscroll.appendf ("resource outputs: `%s`;", self._resource_outputs)
		_subscroll.appendf ("temporary: `%s`;", self._temporary)
		_subscroll.appendf ("timestamp: `%s`;", self._timestamp)
		self._describe_definitions (_subscroll)

_rpm_package_name_re = re.compile ("^.*$")
_rpm_package_version_re = re.compile ("^.*$")
_rpm_package_release_re = re.compile ("^.*$")
_rpm_architecture_re = re.compile ("^.*$")

_resource_uri_re = re.compile ("^.*$")

_target_path_part_pattern = "(?:[a-z0-9._-]+)"
_target_path_part_re = re.compile ("^%s$" % (_target_path_part_pattern,))
_target_path_pattern = "(?:(?:/%s)+)" % (_target_path_part_pattern,)
_target_path_re = re.compile ("^%s$" % (_target_path_pattern,))

_normal_path_part_pattern = "(?:[ -.0-~]+)"
_normal_path_part_re = re.compile ("^%s$" % (_normal_path_part_pattern,))
_normal_path_absolute_pattern = "(?:(?:/%s)+)" % (_normal_path_part_pattern,)
_normal_path_relative_pattern = "(?:(?:%s)(?:/%s)*)" % (_normal_path_part_pattern, _normal_path_part_pattern)
_normal_path_pattern = "(?:%s|%s|/)" % (_normal_path_absolute_pattern, _normal_path_relative_pattern)
_normal_path_re = re.compile ("^%s$" % (_normal_path_pattern,))


class Overlay (object) :
	
	def __init__ (self, _builder, _root, _target) :
		self._root = _root
		self._target = _target
		self._command_arguments = _builder._command_arguments
	
	def instantiate (self) :
		raise _error ("1dc02360")
	
	def describe (self, _scroll) :
		raise _error ("fb80334a")


class UnarchiverOverlay (Overlay) :
	
	def __init__ (self, _builder, _root, _target, _resource, _format, _options) :
		Overlay.__init__ (self, _builder, _root, _target)
		self._resource = _resource
		self._format = _format
		self._options = _options
	
	def instantiate (self) :
		
		_format = _coerce (self._format, basestring)
		if _format == "cpio+gzip" :
			_archive_format = "cpio"
			_stream_format = "gzip"
		elif _format == "tar+gzip" :
			_archive_format = "tar"
			_stream_format = "gzip"
		else :
			raise _error ("bad3ec12", format = self._format)
		
		_commands = []
		
		if _stream_format == "gzip" :
			_gunzip_input, _gunzip_output = _create_pipe_values (None)
			_command = GzipExtractCommand (**self._command_arguments) .instantiate (_gunzip_output, self._resource)
			_commands.append (_command)
			_stream = _gunzip_input
			
		elif _stream_format is None :
			_stream = self._resource
			
		else :
			raise _error ("6534e0ed", format = _stream_format)
		
		_target = PathValue (None, [self._root, self._target])
		
		if _archive_format == "cpio" :
			_command = CpioExtractCommand (**self._command_arguments) .instantiate (_target, _stream, options = self._options)
			_commands.append (_command)
			
		elif _archive_format == "tar" :
			_command = TarExtractCommand (**self._command_arguments) .instantiate (_target, _stream, options = self._options)
			_commands.append (_command)
			
		else :
			raise _error ("wtf!", format = _archive_format)
		
		_commands = ParallelCommandInstance (_commands)
		
		return _commands
	
	def describe (self, _scroll) :
		_scroll.append ("unarchiver overlay:")
		_scroll.appendf ("target: `%s`;", self._target, indentation = 1)
		_scroll.appendf ("resource: `%s`;", self._resource, indentation = 1)
		_scroll.appendf ("format: `%s`;", self._format, indentation = 1)
		_scroll.appendf ("root: `%s`;", self._root, indentation = 1)


class FileCreatorOverlay (Overlay) :
	
	def __init__ (self, _builder, _root, _target, _resource, _executable, _expand, _resolver) :
		Overlay.__init__ (self, _builder, _root, _target)
		self._resource = _resource
		self._executable = _executable
		self._expand = _expand
		self._resolver = _resolver
	
	def instantiate (self) :
		_target = PathValue (None, [self._root, self._target])
		if not self._expand :
			_command = CpCommand (**self._command_arguments) .instantiate (_target, self._resource)
		else :
			_command = ExpandFileCommand (self._resolver, **self._command_arguments) .instantiate (_target, self._resource)
		if self._executable :
			_commands = []
			_commands.append (_command)
			_commands.append (ChmodCommand (**self._command_arguments) .instantiate (_target, "+x"))
			_command = SequentialCommandInstance (_commands)
		return _command
	
	def describe (self, _scroll) :
		_scroll.append ("file creator overlay:")
		_scroll.appendf ("target: `%s`;", self._target, indentation = 1)
		_scroll.appendf ("resource: `%s`;", self._resource, indentation = 1)
		_scroll.appendf ("expand: `%s`;", self._expand, indentation = 1)
		_scroll.appendf ("resolver: `%s`;", repr (self._resolver), indentation = 1)
		_scroll.appendf ("root: `%s`;", self._root, indentation = 1)


class SymlinksOverlay (Overlay) :
	
	def __init__ (self, _builder, _root, _target, _links) :
		Overlay.__init__ (self, _builder, _root, _target)
		self._links = _links
	
	def instantiate (self) :
		_commands = []
		for _target, _source in self._links :
			_target = PathValue (None, [self._root, self._target, _target])
			_commands.append (LnCommand (**self._command_arguments) .instantiate (_target, _source, True))
		return SequentialCommandInstance (_commands)
	
	def describe (self, _scroll) :
		_scroll.append ("symlinks overlay:")
		_scroll.appendf ("target: `%s`;", self._target, indentation = 1)
		_scroll.append ("links:", indentation = 1)
		_links = {}
		for _target, _source in self._links :
			_links[_target] = _source
		for _target in sorted (_links.keys ()) :
			_source = _links[_target]
			_scroll.appendf ("`%s` -> `%s`;", _target, _source, indentation = 2)
		_scroll.appendf ("root: `%s`;", self._root, indentation = 1)


class RenamesOverlay (Overlay) :
	
	def __init__ (self, _builder, _root, _target, _renames) :
		Overlay.__init__ (self, _builder, _root, _target)
		self._renames = _renames
	
	def instantiate (self) :
		_commands = []
		for _target, _source in self._renames :
			_target = PathValue (None, [self._root, self._target, _target])
			_source = PathValue (None, [self._root, self._target, _source])
			_commands.append (MvCommand (**self._command_arguments) .instantiate (_target, _source))
		return SequentialCommandInstance (_commands)
	
	def describe (self, _scroll) :
		_scroll.append ("renames overlay:")
		_scroll.appendf ("target: `%s`;", self._target, indentation = 1)
		_scroll.append ("renames:", indentation = 1)
		_renames = {}
		for _target, _source in self._renames :
			_renames[_target] = _source
		for _target in sorted (_renames.keys ()) :
			_source = _renames[_target]
			_scroll.appendf ("`%s` -> `%s`;", _target, _source, indentation = 2)
		_scroll.appendf ("root: `%s`;", self._root, indentation = 1)

class FoldersOverlay (Overlay) :
	
	def __init__ (self, _builder, _root, _target, _folders) :
		Overlay.__init__ (self, _builder, _root, _target)
		self._folders = _folders
	
	def instantiate (self) :
		_commands = []
		for _target in self._folders :
			_target = PathValue (None, [self._root, self._target, _target])
			_commands.append (MkdirCommand (**self._command_arguments) .instantiate (_target, True))
		return SequentialCommandInstance (_commands)
	
	def describe (self, _scroll) :
		_scroll.append ("folders overlay:")
		_scroll.appendf ("target: `%s`;", self._target, indentation = 1)
		_scroll.append ("folders:", indentation = 1)
		for _target in sorted (self._folders) :
			_scroll.appendf ("`%s`;", _target, indentation = 2)
		_scroll.appendf ("root: `%s`;", self._root, indentation = 1)


class Resource (object) :
	
	def __init__ (self, _builder, _identifier) :
		self._identifier = _identifier
		self._command_arguments = _builder._command_arguments
	
	def instantiate (self) :
		raise _error ("e505577a")
	
	def describe (self, _scroll) :
		raise _error ("4b7ca4e7")


class ClonedResource (Resource) :
	
	def __init__ (self, _builder, _identifier, _inputs, _source, _outputs, _target) :
		Resource.__init__ (self, _builder, _identifier)
		self._inputs = _inputs
		self._source = _source
		self._outputs = _outputs
		self._target = _target
		self.path = PathValue (None, [self._outputs, self._target])
	
	def instantiate (self) :
		_source = PathValue (None, [self._inputs, self._source])
		return CpCommand (**self._command_arguments) .instantiate (self.path, _source)
	
	def describe (self, _scroll) :
		_scroll.append ("sources resource:")
		_scroll.appendf ("identifier: `%s`;", self._identifier, indentation = 1)
		_scroll.appendf ("inputs: `%s`;", self._inputs, indentation = 1)
		_scroll.appendf ("source: `%s`;", self._source, indentation = 1)
		_scroll.appendf ("outputs: `%s`;", self._outputs, indentation = 1)
		_scroll.appendf ("target: `%s`;", self._target, indentation = 1)
		_scroll.appendf ("path: `%s`;", self.path, indentation = 1)


class FetcherResource (Resource) :
	
	def __init__ (self, _builder, _identifier, _uri, _outputs, _target) :
		Resource.__init__ (self, _builder, _identifier)
		self._uri = _uri
		self._outputs = _outputs
		self._target = _target
		self.path = PathValue (None, [self._outputs, self._target])
	
	def instantiate (self) :
		return SafeCurlCommand (**self._command_arguments) .instantiate (self.path, self._uri)
	
	def describe (self, _scroll) :
		_scroll.append ("fetcher resource:")
		_scroll.appendf ("identifier: `%s`;", self._identifier, indentation = 1)
		_scroll.appendf ("uri: `%s`;", self._uri, indentation = 1)
		_scroll.appendf ("outputs: `%s`;", self._outputs, indentation = 1)
		_scroll.appendf ("target: `%s`;", self._target, indentation = 1)
		_scroll.appendf ("path: `%s`;", self.path, indentation = 1)


class Context (object) :
	
	def __init__ (self) :
		self._values = []
		self._resolvable_values = {}
	
	def register_value (self, _identifier, _value) :
		if _context_value_identifier_re.match (_identifier) is None :
			raise _error ("e3f0d909", identifier = _identifier)
		if _identifier in self._resolvable_values :
			raise _error ("4a5a0274", identifier = _identifier)
		self._resolvable_values[_identifier] = _value
		return _value
	
	def resolve_value (self, _identifier) :
		if not _identifier in self._resolvable_values :
			raise _error ("a17bc76a", identifier = _identifier)
		_value = self._resolvable_values[_identifier]
		return _value

_context_value_identifier_part_pattern = "(?:[a-zA-Z0-9](?:[._-]?[a-zA-Z0-9])*)"
_context_value_identifier_pattern = "(?:%s(?::%s)*)" % (_context_value_identifier_part_pattern, _context_value_identifier_part_pattern)
_context_value_identifier_re = re.compile ("^%s$" % (_context_value_identifier_pattern,))


class ContextValue (object) :
	
	def __init__ (self, _context, identifier = None, constraints = None) :
		
		self._context = _context
		self._identifier = identifier
		self._constraints = constraints if constraints is not None and len (constraints) > 0 else None
		self._resolved = False
		self._value = None
		
		if self._identifier is not None :
			self._context.register_value (self._identifier, self)
	
	def __call__ (self) :
		if self._resolved is None :
			raise _error ("6aaade75")
		if not self._resolved :
			self._resolved = None
			_value = self._resolve ()
			if self._constraints is not None :
				for _constraint in self._constraints :
					if not _constraint (_value) :
						raise _error ("9dfbd8e7", value = _value)
			self._value = _value
			self._resolved = True
		return self._value
	
	def _resolve (self) :
		raise _error ("c5ec1b69")
	
	def __str__ (self) :
		return repr (self)
	
	def __repr__ (self) :
		raise _error ("557267b5")


class ConstantValue (ContextValue) :
	
	def __init__ (self, _context, _value, **_arguments) :
		ContextValue.__init__ (self, _context, **_arguments)
		self._constant = _value
	
	def _resolve (self) :
		return self._constant
	
	def __repr__ (self) :
		return repr (self._constant)


class LambdaValue (ContextValue) :
	
	def __init__ (self, _context, _lambda, **_arguments) :
		ContextValue.__init__ (self, _context, **_arguments)
		self._lambda = _lambda
	
	def _resolve (self) :
		return self._lambda ()
	
	def __repr__ (self) :
		return "<LambdaValue: %r>" % (self._lambda,)


class ExpandableStringValue (ContextValue) :
	
	def __init__ (self, _context, _template, pattern = None, constraints = [], **_arguments) :
		
		if constraints is None :
			constraints = []
		if pattern is None :
			pass
		elif isinstance (pattern, type (_expandable_string_template_re)) :
			constraints = [lambda _string : pattern.match (_string) is not None] .extend (constraints)
		elif isinstance (pattern, basestring) :
			constraints = [lambda _string : re.match (pattern, _string) is not None] .extend (constraints)
		
		ContextValue.__init__ (self, _context, constraints = constraints, **_arguments)
		self._template = _template
	
	def _resolve (self) :
		_match = _expandable_string_template_re.match (self._template)
		if _match is None :
			raise _error ("cee1f00b")
		_value = _expand_string_template (self._template, self._context.resolve_value)
		return _value
	
	def __repr__ (self) :
		return self ()

def _expand_string_template (_template, _resolver) :
	def _expand (_identifier_match) :
		_identifier = _identifier_match.group (0) [2 : -1]
		_value = _resolver (_identifier)
		_value = _coerce (_value, None)
		_value = type (_template) (_value)
		return _value
	return re.sub (_expandable_string_template_variable_re, _expand, _template)

_expandable_string_template_variable_pattern = "(?:@\{%s\})" % (_context_value_identifier_pattern,)
_expandable_string_template_variable_re = _expandable_string_template_variable_pattern
_expandable_string_template_pattern = "(?:(?:.*(?:%s).*)*|[^@]*)" % (_expandable_string_template_variable_pattern,)
_expandable_string_template_re = re.compile ("^%s$" % (_expandable_string_template_pattern,))


class PathValue (ContextValue) :
	
	def __init__ (self, _context, _parts, pattern = _normal_path_re, constraints = [], temporary = False, **_arguments) :
		ContextValue.__init__ (self, _context,
				constraints = [
						lambda _path : pattern.match (_path) is not None]
						.extend (constraints),
				**_arguments)
		self._parts = _parts
		self._temporary = temporary
	
	def _resolve (self) :
		_parts = [_coerce (_part, basestring) for _part in self._parts]
		for _index in xrange (len (_parts)) :
			_part = _parts[_index]
			if _part[0] == "/" and _index > 0 :
				_part = "." + _part
			_parts[_index] = _part
		_value = path.join (*_parts)
		_value = path.normpath (_value)
		if self._temporary :
			_value = _resolve_temporary_path (_value)
		return _value
	
	def __repr__ (self) :
		return self ()


class FileValue (ContextValue) :
	
	def __init__ (self, _context, _descriptor, _mode, **_arguments) :
		ContextValue.__init__ (self, _context, **_arguments)
		self._descriptor = _descriptor
		self._mode = _mode
	
	def _resolve (self) :
		_value = _coerce_file (self._descriptor, self._mode)
		return _value
	
	def __repr__ (self) :
		return "<FileValue, descriptor: %r, mode: %r>" % (self._descriptor, self._mode)


def _create_pipe_values (_context, **_arguments) :
	
	_descriptors = [None, None]
	
	def _open () :
		_logger.debug ("opening pipes...")
		_descriptors[0], _descriptors[1] = os.pipe ()
	
	def _input () :
		if _descriptors[0] is None :
			_open ()
		return _descriptors[0]
	
	def _output () :
		if _descriptors[1] is None :
			_open ()
		return _descriptors[1]
	
	return FileValue (_context, _input, "r", **_arguments), FileValue (_context, _output, "w", **_arguments)


class ResolvableValue (ContextValue) :
	
	def __init__ (self, _context, _identifier, _resolver, **_arguments) :
		ContextValue.__init__ (self, _context, **_arguments)
		self._identifier = _identifier
		self._resolver = _resolver
	
	def _resolve (self) :
		_identifier = self._identifier ()
		_value = self._resolver (_identifier)
		return (_value)
	
	def __repr__ (self) :
		return "<ResolvableValue, identifier: %r, resolver: %r>" % (self._identifier, self._resolver)


class LicenseValue (ContextValue) :
	
	def __init__ (self, _context, _identifier, constraints = [], **_arguments) :
		ContextValue.__init__ (self, _context,
				constraints = [
						lambda _identifier : _license_identifier_re.match (_identifier) is not None,
						lambda _identifier : _identifier in _license_rpm_names]
						.extend (constraints),
				**_arguments)
		self._identifier = _identifier
	
	def _resolve (self) :
		return self._identifier ()
	
	def rpm_name (self) :
		return _license_rpm_names[self ()]
	
	def __repr__ (self) :
		return self.rpm_name ()

_license_identifier_pattern = "(?:[a-z0-9]+|[a-z0-9]-(?:[0-9]+|[0-9]+\.[0-9]+))"
_license_identifier_re = re.compile ("^%s$" % (_license_identifier_pattern,))

_license_rpm_names = {
		"apache-2.0" : "Apache 2.0",
}


class Command (object) :
	
	def __init__ (self) :
		pass
	
	def execute (self, *_list_arguments, **_map_arguments) :
		_instance = self.instantiate (*_list_arguments, **_map_arguments)
		return _instance.execute (**_map_arguments)
	
	def instantiate (self, *_list_arguments, **_map_arguments) :
		raise _error ("dcbf0297")


class BasicCommand (Command) :
	
	def __init__ (self, _executable, environment = {}, setarch = None, strace = None) :
		Command.__init__ (self)
		self._executable = _resolve_executable_path (_executable)
		self._argument0 = None
		self._environment = environment
		self._setarch = setarch
		self._strace = strace
	
	def _instantiate_1 (self, _arguments, stdin = None, stdout = None, stderr = None, root = None) :
		
		_wrapper = []
		
		if self._strace is not None :
			_strace_executable = _resolve_executable_path ("strace")
			_strace_arguments = []
			_strace_arguments.extend (["-f"])
			for _strace_event in strace :
				_strace_arguments.extend (["-e", _strace_event])
			_strace_arguments.append ("--")
			
			_wrapper = [_strace_executable] + _strace_arguments + _wrapper
		
		if self._setarch is not None :
			_setarch_executable = _resolve_executable_path ("setarch")
			_setarch_arguments = [self._setarch, "--"]
			
			_wrapper = [_setarch_executable] + _setarch_arguments + _wrapper
		
		if len (_wrapper) == 0 :
			_wrapper = None
		
		if _wrapper is not None :
			_executable = _wrapper[0]
			_argument0 = None
			_arguments = _wrapper[1:] + [self._executable] + _arguments
			
		else :
			_executable = self._executable
			_argument0 = self._argument0
		
		return ExternalCommandInstance (_executable, _argument0, _arguments, self._environment, stdin, stdout, stderr, root)


class MkdirCommand (BasicCommand) :
	
	def __init__ (self, **_arguments) :
		BasicCommand.__init__ (self, "mkdir", **_arguments)
	
	def instantiate (self, _target, _recursive = False) :
		if _recursive :
			return self._instantiate_1 (["-p", "--", _target])
		else :
			return self._instantiate_1 (["--", _target])


class MvCommand (BasicCommand) :
	
	def __init__ (self, **_arguments) :
		BasicCommand.__init__ (self, "mv", **_arguments)
	
	def instantiate (self, _target, _source) :
		return self._instantiate_1 (["-T", "--", _source, _target])


class LnCommand (BasicCommand) :
	
	def __init__ (self, **_arguments) :
		BasicCommand.__init__ (self, "ln", **_arguments)
	
	def instantiate (self, _target, _source, _symbolic = True) :
		if _symbolic :
			return self._instantiate_1 (["-s", "-T", "--", _source, _target])
		else :
			return self._instantiate_1 (["-T", "--", _source, _target])


class CpCommand (BasicCommand) :
	
	def __init__ (self, **_arguments) :
		BasicCommand.__init__ (self, "cp", **_arguments)
	
	def instantiate (self, _target, _source) :
		return self._instantiate_1 (["-T", "-p", "--", _source, _target])


class RmCommand (BasicCommand) :
	
	def __init__ (self, **_arguments) :
		BasicCommand.__init__ (self, "rm", **_arguments)
	
	def instantiate (self, _target, _recursive = False) :
		if _recursive :
			return self._instantiate_1 (["-R", "--", _target])
		else :
			return self._instantiate_1 (["--", _target])


class ChmodCommand (BasicCommand) :
	
	def __init__ (self, **_arguments) :
		BasicCommand.__init__ (self, "chmod", **_arguments)
	
	def instantiate (self, _target, _mode, _recursive = False) :
		if _recursive :
			return self._instantiate_1 (["-R", _mode, "--", _target])
		else :
			return self._instantiate_1 ([_mode, "--", _target])


class ZipExtractCommand (BasicCommand) :
	
	def __init__ (self, **_arguments) :
		BasicCommand.__init__ (self, "unzip", **_arguments)
	
	def instantiate (self, _target, _archive) :
		return self._instantiate_1 (["-b", "-D", "-n", "-q", "-d", _target, "--", _archive])


class SafeZipExtractCommand (Command) :
	
	def __init__ (self, **_arguments) :
		Command.__init__ (self)
		self._mkdir = MkdirCommand (**_arguments)
		self._unzip = ZipExtractCommand (**_arguments)
		self._mv = MvCommand (**_arguments)
	
	def instantiate (self, _target, _archive, **_arguments) :
		_safe_target = _resolve_temporary_path (_target)
		_mkdir = self._mkdir.instantiate (_safe_target)
		_unzip = self._unzip.instantiate (_safe_target, _archive, **_arguments)
		_mv = self._mv.instantiate (_target, _safe_target)
		return SequentialCommandInstance ([_mkdir, _unzip, _mv])


class GzipExtractCommand (BasicCommand) :
	
	def __init__ (self, **_arguments) :
		BasicCommand.__init__ (self, "gzip", **_arguments)
	
	def instantiate (self, _target, _input) :
		return self._instantiate_1 (["-d", "-c"], stdin = _input, stdout = _target)


class CpioExtractCommand (BasicCommand) :
	
	def __init__ (self, **_arguments) :
		BasicCommand.__init__ (self, "cpio", **_arguments)
	
	def instantiate (self, _target, _input, options = None) :
		if options is not None and len (options) > 0 :
			raise _error ("wtf!")
		return self._instantiate_1 (
				["-i", "-H", "newc", "--make-directories", "--no-absolute-filenames", "--no-preserve-owner", "--quiet"],
				stdin = _input, root = _target)


class SafeCpioExtractCommand (Command) :
	
	def __init__ (self, **_arguments) :
		Command.__init__ (self)
		self._mkdir = MkdirCommand (**_arguments)
		self._cpio = CpioExtractCommand (**_arguments)
		self._mv = MvCommand (**_arguments)
	
	def instantiate (self, _target, _archive, **_arguments) :
		_safe_target = _resolve_temporary_path (_target)
		_mkdir = self._mkdir.instantiate (_safe_target)
		_cpio = self._cpio.instantiate (_safe_target, _archive, **_arguments)
		_mv = self._mv.instantiate (_target, _safe_target)
		return SequentialCommandInstance ([_mkdir, _cpio, _mv])


class TarExtractCommand (BasicCommand) :
	
	def __init__ (self, **_arguments) :
		BasicCommand.__init__ (self, "tar", **_arguments)
	
	def instantiate (self, _target, _input, options = None) :
		
		_arguments = []
		_arguments.extend ([
				"--extract",
				"--directory", _target,
		])
		_arguments.extend ([
						"--delay-directory-restore",
						"--no-overwrite-dir",
						"--preserve-permissions",
						"--no-same-owner",
		])
		
		if options is not None :
			for _option, _value in options.items () :
				if _option == "strip-components" :
					_arguments.extend (["--transform", "s%^\./%%"])
					_arguments.extend (["--strip-components", str (_coerce (_value, int))])
				else :
					raise _error ("wtf!")
		
		return self._instantiate_1 (_arguments, stdin = _input)


class SafeTarExtractCommand (Command) :
	
	def __init__ (self, **_arguments) :
		Command.__init__ (self)
		self._mkdir = MkdirCommand (**_arguments)
		self._tar = TarExtractCommand (**_arguments)
		self._mv = MvCommand (**_arguments)
	
	def instantiate (self, _target, _archive, **_arguments) :
		_safe_target = _resolve_temporary_path (_target)
		_mkdir = self._mkdir.instantiate (_safe_target)
		_tar = self._tar.instantiate (_safe_target, _archive, **_arguments)
		_mv = self._mv.instantiate (_target, _safe_target)
		return SequentialCommandInstance ([_mkdir, _tar, _mv])


class CurlCommand (BasicCommand) :
	
	def __init__ (self, **_arguments) :
		BasicCommand.__init__ (self, "curl", **_arguments)
	
	def instantiate (self, _target, _uri) :
		return self._instantiate_1 (["-s", "-f", "-o", _target, "--retry", "3", "--", _uri])


class SafeCurlCommand (Command) :
	
	def __init__ (self, **_arguments) :
		Command.__init__ (self)
		self._curl = CurlCommand (**_arguments)
		self._mv = MvCommand (**_arguments)
	
	def instantiate (self, _target, _uri, **_arguments) :
		_safe_target = PathValue (None, [_target], temporary = True)
		_curl = self._curl.instantiate (_safe_target, _uri, **_arguments)
		_mv = self._mv.instantiate (_target, _safe_target)
		return SequentialCommandInstance ([_curl, _mv])


class ExpandFileCommand (Command) :
	
	def __init__ (self, _resolver, **_arguments) :
		Command.__init__ (self)
		self._resolver = _resolver
		self._create = FileCreateCommand (**_arguments)
		self._mv = MvCommand (**_arguments)
	
	def instantiate (self, _target, _source) :
		_safe_target = PathValue (None, [_target], temporary = True)
		def _chunks () :
			with _coerce_file (_source, "r") as _stream :
				for _line in _stream :
					_line = self._expand (_line)
					yield _line
		_create = self._create.instantiate (_safe_target, _chunks)
		_mv = self._mv.instantiate (_target, _safe_target)
		return SequentialCommandInstance ([_create, _mv])
	
	def _expand (self, _line) :
		return _expand_string_template (_line, self._resolver)


class RpmBuildCommand (BasicCommand) :
	
	def __init__ (self, **_arguments) :
		BasicCommand.__init__ (self, "rpmbuild", **_arguments)
	
	def instantiate (self, _spec, rpm_macros = None, rpm_buildroot = None, rpm_buildtarget = None, rpm_defines = None, rpm_rc = None, rpm_db = None, quiet = True, debug = False) :
		
		_arguments = []
		
		_arguments.append ("-bb")
		if quiet :
			_arguments.append ("--quiet")
		elif debug :
			_arguments.append ("-vv")
		
		if rpm_rc is not None :
			_arguments.extend (["--rcfile", rpm_rc])
		if rpm_db is not None :
			_arguments.extend (["--dbpath", rpm_db])
		
		if rpm_macros is not None :
			_arguments.extend (["--macros", rpm_macros])
		if rpm_buildroot is not None :
			_arguments.extend (["--buildroot", rpm_buildroot])
		if rpm_buildtarget is not None :
			_arguments.extend (["--target", rpm_buildtarget])
		
		if rpm_defines is not None :
			for _name, _value in rpm_defines.items () :
				def _define_lambda (_name, _value) :
					return LambdaValue (None, lambda : "%s %s" % (_coerce (_name, basestring), _coerce (_value, basestring)))
				_arguments.extend (["--define", _define_lambda (_name, _value)])
		
		_arguments.append ("--")
		_arguments.append (_spec)
		
		return self._instantiate_1 (_arguments)


class SequentialCommandInstance (object) :
	
	def __init__ (self, _commands) :
		self._commands = _commands
	
	def execute (self, wait = True) :
		if not wait :
			raise _error ("0d2b6697")
		for _command in self._commands :
			_command.execute (wait = True)
		if wait :
			self.wait ()
	
	def wait (self) :
		for _command in self._commands :
			_command.wait ()
	
	def describe (self, _scroll) :
		_scroll.append ("sequential commands:")
		_subscroll = _scroll.splice (indentation = 1)
		for _command in self._commands :
			_command.describe (_subscroll)


class ParallelCommandInstance (object) :
	
	def __init__ (self, _commands) :
		self._commands = _commands
	
	def execute (self, wait = True) :
		for _command in self._commands :
			_command.execute (wait = False)
		if wait :
			self.wait ()
	
	def wait (self) :
		for _command in self._commands :
			_command.wait ()
	
	def describe (self, _scroll) :
		_scroll.append ("parallel commands:")
		_subscroll = _scroll.splice (indentation = 1)
		for _command in self._commands :
			_command.describe (_subscroll)


class ExternalCommandInstance (object) :
	
	def __init__ (self, _executable, _argument0, _arguments, _environment, _stdin, _stdout, _stderr, _root) :
		self._executable = _executable
		self._argument0 = _argument0 or path.basename (self._executable)
		self._arguments = _arguments or []
		self._environment = _environment or os.environ
		self._stdin = _stdin
		self._stdout = _stdout
		self._stderr = _stderr
		self._root = _root or os.environ.get ("TMPDIR") or "/tmp"
		self._process = None
	
	def execute (self, wait = True) :
		
		if self._process is not None :
			raise _error ("42421ef4")
		
		_executable = _coerce (self._executable, basestring)
		_argument0 = _coerce (self._argument0, basestring)
		_arguments = [_coerce (_argument, basestring) for _argument in self._arguments]
		_environment = {_coerce (_name, basestring) : _coerce (_value, basestring) for _name, _value in self._environment.items ()}
		_stdin = _coerce_file (self._stdin, "r", True)
		_stdout = _coerce_file (self._stdout, "w", True)
		_stderr = _coerce_file (self._stderr, "w", True)
		_root = _coerce (self._root, basestring)
		
		if _stdin is not None :
			_stdin_1 = None
		else :
			_stdin_1, _stdin_2 = os.pipe ()
			os.close (_stdin_2)
			_stdin = _stdin_1
		if _stdout is not None :
			_stdout_1 = None
		else :
			_stdout_2, _stdout_1 = os.pipe ()
			os.close (_stdout_2)
			_stdout = _stdout_1
		if _stderr is not None :
			pass
		else :
			_stderr = sys.stderr
		
		_stdin = _coerce_file (_stdin, "r")
		_stdout = _coerce_file (_stdout, "w")
		_stderr = _coerce_file (_stderr, "w")
		
		_logger.debug ("executing `%s %s`...", _argument0, " ".join (_arguments))
		
		self._process = subprocess.Popen (
				[_argument0] + _arguments,
				executable = _executable,
				stdin = _stdin,
				stdout = _stdout,
				stderr = _stderr,
				close_fds = True,
				cwd = _root,
				env = _environment)
		
		if _stdin_1 is not None :
			_stdin.close ()
		if _stdout_1 is not None :
			_stdout.close ()
		
		if wait :
			self.wait ()
	
	def wait (self) :
		
		_outcome = self._process.wait ()
		
		if _outcome != 0 :
			raise _error ("39199a54", outcome = _outcome)
	
	def describe (self, _scroll) :
		_scroll.append ("external command:")
		_scroll.appendf ("executable: `%s`;", self._executable, indentation = 1)
		_scroll.appendf ("argument0: `%s`;", self._argument0, indentation = 1)
		_scroll.appendf ("arguments: `%s`;", lambda : "`, `".join ([str (_argument) for _argument in self._arguments]), indentation = 1)
		_scroll.appendf ("stdin: `%s`;", self._stdin, indentation = 1)
		_scroll.appendf ("stdout: `%s`;", self._stdout, indentation = 1)
		_scroll.appendf ("stderr: `%s`;", self._stderr, indentation = 1)
		_scroll.appendf ("root: `%s`;", self._root, indentation = 1)


class FileCreateCommand (Command) :
	
	def __init__ (self, **_arguments) :
		Command.__init__ (self)
	
	def instantiate (self, _target, _chunks) :
		return FileCreateCommandInstance (_target, _chunks)


class FileCreateCommandInstance (object) :
	
	def __init__ (self, _target, _chunks) :
		self._target = _target
		self._chunks = _chunks
	
	def execute (self, wait = True) :
		_chunks = _coerce (self._chunks, None)
		with _coerce_file (self._target, "w") as _stream :
			for _chunk in _chunks :
				_stream.write (_chunk)
	
	def wait (self) :
		pass
	
	def describe (self, _scroll) :
		_scroll.append ("file create command:")
		_scroll.appendf ("target: `%s`;", self._target, indentation = 1)
		_scroll.appendf ("chunks: `%s`;", repr (self._chunks), indentation = 1)


class SafeFileCreateCommand (Command) :
	
	def __init__ (self, **_arguments) :
		Command.__init__ (self)
		self._create = FileCreateCommand (**_arguments)
		self._mv = MvCommand (**_arguments)
	
	def instantiate (self, _target, _chunks, **_arguments) :
		_safe_target = PathValue (None, [_target], temporary = True)
		_create = self._create.instantiate (_safe_target, _chunks, **_arguments)
		_mv = self._mv.instantiate (_target, _safe_target)
		return SequentialCommandInstance ([_create, _mv])


class Scroll (object) :
	
	def __init__ (self) :
		self._blocks = []
	
	def append (self, _string, **_modifiers) :
		self.include_lines ([_string], **_modifiers)
	
	def appendf (self, _format, *_parts, **_modifiers) :
		_line = [_format]
		_line.extend (_parts)
		_line = tuple (_line)
		self.include_lines ([_line], **_modifiers)
	
	def include_lines (self, _lines, priority = 0, indentation = 0) :
		_block = (_lines, priority, indentation)
		self._blocks.append (_block)
	
	def include_scroll (self, _scroll, priority = 0, indentation = 0) :
		_block = (_scroll, priority, indentation)
		self._blocks.append (_block)
	
	def splice (self, **_modifiers) :
		_scroll = Scroll ()
		self.include_scroll (_scroll, **_modifiers)
		return _scroll
	
	def lines (self) :
		for _line, _indentation in self._lines () :
			_line = self._format (_line, _indentation)
			yield _line
	
	def lines_with_nl (self) :
		for _line in self.lines () :
			_line = _line + "\n"
			yield _line
	
	def _lines (self) :
		
		_blocks = sorted (self._blocks, lambda _left, _right : _left[1] < _right[1])
		
		for _lines, _priority, _indentation in _blocks :
			
			if isinstance (_lines, Scroll) :
				for _line, _indentation_1 in _lines._lines () :
					yield _line, _indentation + _indentation_1
				
			elif isinstance (_lines, list) :
				for _line in _lines :
					if isinstance (_line, basestring) or isinstance (_line, tuple) :
						yield _line, _indentation
					else :
						raise _error ("6d472c53")
				
			else :
				raise _error ("9b817186")
	
	def _format (self, _line, _indentation) :
		
		if isinstance (_line, basestring) :
			pass
			
		elif isinstance (_line, tuple) :
			_format = _line[0]
			_parts = tuple ([_coerce (_part, (basestring, int, long, float, complex, ContextValue), True) for _part in _line[1:]])
			_line = _format % _parts
			
		else :
			raise _error ("22469e17")
		
		_line = ("\t" * _indentation) + _line
		
		return _line
	
	def output (self, _stream) :
		for _line in self.lines_with_nl () :
			_stream.write (_line)
		_stream.flush ()
	
	def stream (self, _stream) :
		for _line in self.lines () :
			_stream (_line)



def _mkdirs (_path) :
	if path.isdir (_path) :
		return
	if path.exists (_path) :
		raise _error ("8790dabf")
	_logger.debug ("creating folder `%s`...", _path)
	os.makedirs (_path)


def _json_load (_path) :
	_logger.debug ("loading JSON from `%s`...", _path)
	with open (_path, "r") as _stream :
		return json.load (_stream)

def _json_select (_root, _keys, _type, required = True, default = None) :
	for _key in _keys :
		if isinstance (_key, basestring) :
			if not isinstance (_root, dict) :
				raise _error ("ffb8eb08", root = _root)
			elif _key in _root :
				_root = _root[_key]
			elif required :
				raise _error ("a56daa10", key = _key)
			else :
				_root = default
				break
		elif isinstance (_key, int) :
			if not isinstance (_root, list) :
				raise _error ("d742b4cf", root = _root)
			else :
				_root = _root[_key]
		else :
			raise _error ("837f2c4f", key = _key)
	if not isinstance (_root, _type) :
		raise _error ("376bc11b", root = _root, type = _type)
	return _root


def _resolve_executable_path (_name) :
	# FIXME: !!!
	for _prefix in ["/usr/local/bin", "/usr/bin", "/bin"] :
		_path = path.join (_prefix, _name)
		if path.exists (_path) :
			return _path
	raise _error ("wtf!")


def _resolve_temporary_path (_target) :
	return "%s/.temporary--%s--%s" % (path.dirname (_target), path.basename (_target), _create_token ())


def _create_token () :
	return uuid.uuid4 () .hex


def _coerce (_object, _type, _none_allowed = False) :
	while True :
		if _object is None and _none_allowed :
			break
		if _type is not None:
			if isinstance (_type, type) :
				if isinstance (_object, _type) :
					break
			elif isinstance (_type, tuple) :
				_ok = False
				for _type_1 in _type :
					if isinstance (_object, _type_1) :
						_ok = True
						break
				if _ok :
					break
			else :
				raise _error ("f0188962")
		if callable (_object) :
			_object = _object ()
			continue
		if _type is None :
			break
		raise _error ("b6e3ff7d", object = _object, type = _type)
	return _object


def _coerce_file (_object, _mode, _none_allowed = False) :
	_object = _coerce (_object, (file, basestring, int), _none_allowed)
	if _object is None and _none_allowed :
		_file = None
	elif isinstance (_object, basestring) :
		_logger.debug ("opening file `%s` with mode `%s`...", _object, _mode)
		_file = open (_object, _mode)
	elif isinstance (_object, int) :
		_file = os.fdopen (_object, _mode)
	elif isinstance (_object, file) :
		_file = _object
	else :
		raise _error ("0c0e6555")
	return _file


def _error (_code, **_attributes) :
	def _repr (_value) :
		try :
			if _value is not None :
				return _value.__repr__ ()
			else :
				return "None"
		except :
			return "<error>"
	if _attributes :
		_attribute_list = "; ".join (["%s := `%s`" % (_name, _repr (_attributes[_name])) for _name in sorted (_attributes.keys ())])
		_message = "mpb-error: %s; %s" % (_code, _attribute_list)
	else :
		_message = "mpb-error: %s" % (_code,)
	return Exception (_message)


import logging
logging.basicConfig ()
_logger = logging.getLogger ("mosaic-mpb")
_logger.setLevel (logging.DEBUG)


if __name__ == "__wrapped__" :
	
	_main (__configuration__)
	
	__exit__ (0)
	
elif __name__ == "__main__" :
	
	_configuration = {
			
			"descriptor" : None,
			"sources" : None,
			"package" : None,
			"workbench" : None,
			"temporary" : None,
			
			"package-name" : None,
			"package-version" : None,
			"package-release" : None,
			"package-distribution" : None,
			
			"execute" : True,
	}
	
	if len (sys.argv) == 2 :
		_workbench = sys.argv[1]
		_sources = None
		_package = None
		_descriptor = None
		
	elif len (sys.argv) == 3 :
		if sys.argv[1].endswith (".json") :
			_descriptor = sys.argv[1]
			_sources = None
		elif sys.argv[1].endswith (".zip") or sys.argv[1].endswith (".tar") or sys.argv[1].endswith (".cpio") :
			_sources = sys.argv[1]
			_descriptor = None
		elif path.isdir (sys.argv[1]) :
			_sources = sys.argv[1]
			_descriptor = None
		else :
			raise _error ("5dd6673e")
		if sys.argv[2].endswith (".rpm") :
			_package = sys.argv[2]
		else :
			raise _error ("820aaabe")
		_workbench = None
		
	else :
		raise _error ("42aaf640")
	
	_configuration["descriptor"] = _descriptor
	_configuration["sources"] = _sources
	_configuration["package"] = _package
	_configuration["workbench"] = _workbench
	
	#if os.environ.get ("__execute__") != "__true__" :
	#	_configuration["execute"] = False
	
	_main (_configuration)
	
	sys.exit (0)
	
else :
	raise _error ("eab7d4a5")
