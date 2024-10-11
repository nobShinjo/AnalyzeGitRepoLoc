"""
Attributes:
    extensions (dict): A dictionary of languages and their extensions.
Methods:
    get_extensions(language: str) -> list[str]:
        Get the extensions for a given language.
"""


class LanguageExtensions:
    """
    Class to get the extensions for a given language.
    """

    language_to_extensions: dict[str, list[str]] = {
        "ABAP": [".abap"],
        "ActionScript": [".as"],
        "Ada": [".ada", ".adb", ".ads", ".pad"],
        "ADSO/IDSM": [".adso"],
        "Agda": [".agda", ".lagda"],
        "AMPLE": [".ample", ".dofile", ".startup"],
        "Ant": [".build.xml", ".build.xml"],
        "ANTLR Grammar": [".g", ".g4"],
        "Apex Class": [".cls"],
        "Apex Trigger": [".trigger"],
        "APL": [
            ".apl",
            ".apla",
            ".aplc",
            ".aplf",
            ".apli",
            ".apln",
            ".aplo",
            ".dyalog",
            ".dyapp",
            ".mipag",
        ],
        "Arduino Sketch": [".ino", ".pde"],
        "AsciiDoc": [".adoc", ".asciidoc"],
        "ASP": [".asa", ".ashx", ".asp", ".axd"],
        "ASP.NET": [
            ".asax",
            ".ascx",
            ".asmx",
            ".aspx",
            ".master",
            ".sitemap",
            ".webinf",
        ],
        "AspectJ": [".aj"],
        "Assembly": [".a51", ".asm", ".nasm", ".S", ".s"],
        "Asymptote": [".asy"],
        "AutoHotkey": [".ahk", ".ahkl"],
        "awk": [".auk", ".awk", ".gawk", ".mawk", ".nawk"],
        "Bazel": [".BUILD"],
        "BizTalk Orchestration": [".odx"],
        "BizTalk Pipeline": [".btp"],
        "Blade": [".blade", ".blade.php"],
        "Bourne Again Shell": [".bash"],
        "Bourne Shell": [".sh"],
        "BrightScript": [".brs"],
        "builder": [".xml.builder"],
        "C": [".c", ".cats", ".ec", ".idc", ".pgc"],
        "C Shell": [".csh", ".tcsh"],
        "C#": [".cs"],
        "C# Designer": [".designer.cs"],
        "C++": [
            ".C",
            ".c++",
            ".c++m",
            ".cc",
            ".ccm",
            ".CPP",
            ".cpp",
            ".cppm",
            ".cxx",
            ".cxxm",
            ".h++",
            ".inl",
            ".ipp",
            ".ixx",
            ".pcc",
            ".tcc",
            ".tp",
        ],
        "C/C++ Header": [".H", ".h", ".hh", ".hpp", ".hxx"],
        "Cairo": [".cairo"],
        "Cake Build Script": [".cake"],
        "Carbon": [".carbon"],
        "CCS": [".ccs"],
        "Chapel": [".chpl"],
        "Circom": [".circom"],
        "Clean": [".dcl", ".icl"],
        "Clojure": [
            ".boot",
            ".cl2",
            ".clj",
            ".cljs.hl",
            ".cljscm",
            ".cljx",
            ".hic",
            ".riemann.confi",
        ],
        "ClojureC": [".cljc"],
        "ClojureScript": [".cljs"],
        "CMake": [".cmake", ".cmake.in", ".CMakeLists.txt"],
        "COBOL": [".CBL", ".cbl", ".ccp", ".COB", ".cob", ".cobol", ".cp"],
        "CoCoA 5": [".c5", ".cocoa5", ".cocoa5server", ".cpkg5"],
        "CoffeeScript": ["._coffee", ".cakefile", ".cjsx", ".coffee", ".ice"],
        "ColdFusion": [".cfm", ".cfml"],
        "ColdFusion CFScript": [".cfc"],
        "Constraint Grammar": [".cg3", ".rlx"],
        "Containerfile": [".Containerfile"],
        "Coq": [".v"],
        "Crystal": [".cr"],
        "CSON": [".cson"],
        "CSS": [".css"],
        "CSV": [".csv"],
        "Cucumber": [".feature"],
        "CUDA": [".cu", ".cuh"],
        "Cython": [".pxd", ".pxi", ".pyx"],
        "D": [".d"],
        "DAL": [".da"],
        "Dart": [".dart"],
        "Delphi Form": [".dfm"],
        "DenizenScript": [".dsc"],
        "Derw": [".derw"],
        "dhall": [".dhall"],
        "DIET": [".dt"],
        "diff": [".diff", ".patch"],
        "DITA": [".dita"],
        "Dockerfile": [".Dockerfile", ".dockerfile"],
        "DOORS Extension Language": [".dxl"],
        "DOS Batch": [".BAT", ".bat", ".BTM", ".btm", ".CMD", ".cmd"],
        "Drools": [".drl"],
        "DTD": [".dtd"],
        "dtrace": [".d"],
        "ECPP": [".ecpp"],
        "EEx": [".eex"],
        "EJS": [".ejs"],
        "Elixir": [".ex", ".exs"],
        "Elm": [".elm"],
        "Embedded Crystal": [".ecr"],
        "ERB": [".ERB", ".erb"],
        "Erlang": [
            ".app.src",
            ".emakefile",
            ".erl",
            ".hrl",
            ".rebar.config",
            ".rebar.config.lock",
            ".rebar.lock",
            ".xrl",
            ".yr",
        ],
        "Expe.ct": [".exp"],
        "F#": [".fsi", ".fs", ".fs"],
        "F# Script": [".fsx"],
        "Fennel": [".fnl"],
        "Finite State Language": [".fsl", ".jssm"],
        "Fish Shell": [".fish"],
        "Flatbuffers": [".fbs"],
        "Focus": [".focexec"],
        "Forth": [
            ".4th",
            ".e4",
            ".f83",
            ".fb",
            ".forth",
            ".fpm",
            ".fr",
            ".frt",
            ".ft",
            ".fth",
            ".rx",
            ".fs",
            ".f",
            ".fo",
        ],
        "Fortran 77": [
            ".F",
            ".F77",
            ".f77",
            ".FOR",
            ".FTN",
            ".ftn",
            ".pfo",
            ".f",
            ".fo",
        ],
        "Fortran 90": [".F90", ".f90"],
        "Fortran 95": [".F95", ".f95"],
        "Freemarker Template": [".ftl"],
        "Futhark": [".fut"],
        "FXML": [".fxml"],
        "GDScript": [".gd"],
        "Gencat NLS": [".msg"],
        "Glade": [".glade", ".ui"],
        "Gleam": [".gleam"],
        "GLSL": [
            ".comp",
            ".fp",
            ".frag",
            ".frg",
            ".fsh",
            ".fshader",
            ".geo",
            ".geom",
            ".glsl",
            ".glslv",
            ".gshader",
            ".tesc",
            ".tese",
            ".vert",
            ".vrx",
            ".vsh",
            ".vshade",
        ],
        "Go": [".go"],
        "Godot Resource": [".tres"],
        "Godot Scene": [".tscn"],
        "Godot Shaders": [".gdshader"],
        "Gradle": [".gradle", ".gradle.kts"],
        "Grails": [".gsp"],
        "GraphQL": [".gql", ".graphql", ".graphqls"],
        "Groovy": [".gant", ".groovy", ".grt", ".gtpl", ".gvy", ".jenkinsfil"],
        "Haml": [".haml", ".haml.deface"],
        "Handlebars": [".handlebars", ".hbs"],
        "Harbour": [".hb"],
        "Hare": [".ha"],
        "Haskell": [".hs", ".hsc", ".lhs"],
        "Haxe": [".hx", ".hxsl"],
        "HCL": [".hcl", ".nomad", ".tf", ".tfvars"],
        "HLSL": [".cg", ".cginc", ".fxh", ".hlsl", ".hlsli", ".shade"],
        "HolyC": [".HC"],
        "Hoon": [".hoon"],
        "HTML": [".htm", ".html", ".html.hl", ".xht"],
        "HTML EEx": [".heex"],
        "IDL": [".dlm", ".idl", ".pro"],
        "Idris": [".idr"],
        "Igor Pro": [".ipf"],
        "Imba": [".imba"],
        "INI": [".buildozer.spec", ".editorconfig", ".ini", ".lektorproject", ".pref"],
        "InstallShield": [".ism"],
        "IPL": [".ipl"],
        "Jai": [".jai"],
        "Java": [".java"],
        "JavaScript": [
            "._js",
            ".bones",
            ".cjs",
            ".es6",
            ".jake",
            ".jakefile",
            ".js",
            ".jsb",
            ".jscad",
            ".jsfl",
            ".jsm",
            ".jss",
            ".mjs",
            ".njs",
            ".pac",
            ".sjs",
            ".ssjs",
            ".xsjs",
            ".xsjsli",
        ],
        "JavaServer Faces": [".jsf"],
        "JCL": [".jcl"],
        "Jinja Template": [".jinja", ".jinja2"],
        "JSON": [
            ".arcconfig",
            ".avsc",
            ".composer.lock",
            ".geojson",
            ".gltf",
            ".har",
            ".htmlhintrc",
            ".json",
            ".json-tmlanguage",
            ".jsonl",
            ".mcmeta",
            ".mcmod.info",
            ".tern-config",
            ".tern-project",
            ".tfstate",
            ".tfstate.backup",
            ".topojson",
            ".watchmanconfig",
            ".webapp",
            ".webmanifest",
            ".yy",
        ],
        "JSON5": [".json5"],
        "JSP": [".jsp", ".jspf"],
        "JSX": [".jsx"],
        "Julia": [".jl"],
        "Juniper Junos": [".junos"],
        "Jupyter Notebook": [".ipynb"],
        "Kermit": [".ksc"],
        "Korn Shell": [".ksh"],
        "Kotlin": [".kt", ".ktm", ".kts"],
        "kvlang": [".kv"],
        "Lean": [".hlean", ".lean"],
        "Lem": [".lem"],
        "LESS": [".less"],
        "lex": [".l", ".lex"],
        "LFE": [".lfe"],
        "Linker Script": [".ld"],
        "liquid": [".liquid"],
        "Lisp": [".asd", ".el", ".lisp", ".lsp", ".cl", ".jl"],
        "Literate Idris": [".lidr"],
        "LiveLink OScript": [".oscript"],
        "LLVM IR": [".ll"],
        "Logos": [".x", ".xm"],
        "Logtalk": [".lgt", ".logtalk"],
        "Lua": [".lua", ".nse", ".p8", ".pd_lua", ".rbxs", ".wlu"],
        "m4": [".ac", ".m4"],
        "make": [".am", ".Gnumakefile", ".gnumakefile", ".Makefile", ".makefile", ".m"],
        "Mako": [".mako", ".mao"],
        "Markdown": [
            ".contents.lr",
            ".markdown",
            ".md",
            ".mdown",
            ".mdwn",
            ".mdx",
            ".mkd",
            ".mkdn",
            ".mkdown",
            ".ronn",
            ".workboo",
        ],
        "Mathematica": [".cdf", ".ma", ".mathematica", ".mt", ".nbp", ".wl", ".wlt,"],
        "MATLAB": [".m"],
        "Maven": [".pom", ".pom.xml"],
        "Meson": [".meson.build"],
        "Metal": [".metal"],
        "Modula3": [".i3", ".ig", ".m3", ".mg"],
        "Mojo": [".mojom"],
        "MSBuild script": [
            ".btproj",
            ".csproj",
            ".msbuild",
            ".vcproj",
            ".wdproj",
            ".wixpro",
        ],
        "MUMPS": [".mps", ".m"],
        "Mustache": [".mustache"],
        "MXML": [".mxml"],
        "NAnt script": [".build"],
        "NASTRAN DMAP": [".dmap"],
        "Nemerle": [".n"],
        "NetLogo": [".nlogo", ".nls"],
        "Nim": [".nim", ".nim.cfg", ".nimble", ".nimrod", ".nim"],
        "Nix": [".nix"],
        "Nunjucks": [".njk"],
        "Objective-C": [".m"],
        "Objective-C++": [".mm"],
        "OCaml": [".eliom", ".eliomi", ".ml", ".ml4", ".mli", ".mll", ".ml"],
        "Odin": [".odin"],
        "OpenCL": [".cl"],
        "OpenSCAD": [".scad"],
        "Oracle Forms": [".fmt"],
        "Oracle PL/SQL": [".bod", ".fnc", ".prc", ".spc", ".trg"],
        "Oracle Reports": [".rex"],
        "P4": [".p4"],
        "Pascal": [".dpr", ".lpr", ".p", ".pas", ".pascal"],
        "Pascal/Puppet": [".pp"],
        "Patran Command Language": [".pcl", ".ses"],
        "PEG": [".peg"],
        "peg.js": [".pegjs"],
        "peggy": [".peggy"],
        "Perl": [
            ".ack",
            ".al",
            ".cpanfile",
            ".makefile.pl",
            ".perl",
            ".ph",
            ".plh",
            ".plx",
            ".pm",
            ".psgi",
            ".rexfile",
            ".pl",
            ".p",
        ],
        "Pest": [".pest"],
        "PHP": [
            ".aw",
            ".ctp",
            ".phakefile",
            ".php",
            ".php3",
            ".php4",
            ".php5",
            ".php_cs",
            ".php_cs.dist",
            ".phps",
            ".phpt",
            ".phtm",
        ],
        "PHP/Pascal": [".inc"],
        "Pig Latin": [".pig"],
        "PL/I": [".pl1"],
        "PL/M": [".lit", ".plm"],
        "PlantUML": [".puml"],
        "PO File": [".po"],
        "Pony": [".pony"],
        "PowerBuilder": [".pbt", ".sra", ".srf", ".srm", ".srs", ".sru", ".sr"],
        "PowerShell": [".ps1", ".psd1", ".psm1"],
        "ProGuard": [".pro"],
        "Prolog": [".P", ".prolog", ".yap", ".pl", ".p6", ".pro"],
        "Properties": [".properties"],
        "Protocol Buffers": [".proto"],
        "Pug": [".jade", ".pug"],
        "PureScript": [".purs"],
        "Python": [
            ".buck",
            ".build.bazel",
            ".gclient",
            ".gyp",
            ".gypi",
            ".lmi",
            ".py",
            ".py3",
            ".pyde",
            ".pyi",
            ".pyp",
            ".pyt",
            ".pyw",
            ".sconscript",
            ".sconstruct",
            ".snakefile",
            ".tac",
            ".workspace",
            ".wscript",
            ".wsgi",
            ".xp",
        ],
        "QML": [".qbs", ".qml"],
        "Qt": [".ui"],
        "Qt Linguist": [".ts"],
        "Qt Project": [".pro"],
        "R": [".expr-dist", ".R", ".r", ".rd", ".rprofile", ".rs"],
        "Racket": [".rkt", ".rktd", ".rktl", ".scrbl"],
        "Raku": [".pm6", ".raku", ".rakumod"],
        "Raku/Prolog": [".P6", ".p6"],
        "RAML": [".raml"],
        "RapydScript": [".pyj"],
        "Razor": [".cshtml", ".razor"],
        "ReasonML": [".re", ".rei"],
        "ReScript": [".res", ".resi"],
        "reStructuredText": [".rest", ".rest.txt", ".rst", ".rst.txt"],
        "Rexx": [".pprx", ".rexx"],
        "Ring": [".rform", ".rh", ".ring"],
        "Rmd": [".Rmd"],
        "RobotFramework": [".robot"],
        "Ruby": [
            ".appraisals",
            ".berksfile",
            ".brewfile",
            ".builder",
            ".buildfile",
            ".capfile",
            ".dangerfile",
            ".deliverfile",
            ".eye",
            ".fastfile",
            ".gemfile",
            ".gemfile.lock",
            ".gemspec",
            ".god",
            ".guardfile",
            ".irbrc",
            ".jarfile",
            ".jbuilder",
            ".mavenfile",
            ".mspec",
            ".podfile",
            ".podspec",
            ".pryrc",
            ".puppetfile",
            ".rabl",
            ".rake",
            ".rb",
            ".rbuild",
            ".rbw",
            ".rbx",
            ".ru",
            ".snapfile",
            ".thor",
            ".thorfile",
            ".vagrantfile",
            ".watch",
        ],
        "Ruby HTML": [".rhtml"],
        "Rust": [".rs", ".rs.in"],
        "SaltStack": [".sls"],
        "SAS": [".sas"],
        "Sass": [".sass"],
        "Scala": [".kojo", ".sbt", ".scala"],
        "Scheme": [".sc", ".sch", ".scm", ".sld", ".sps", ".ss", ".sls"],
        "SCSS": [".scss"],
        "sed": [".sed"],
        "SKILL": [".il"],
        "SKILL++": [".ils"],
        "Slice": [".ice"],
        "Slim": [".slim"],
        "Smalltalk": [".st", ".cs"],
        "Smarty": [".smarty", ".tpl"],
        "Softbridge Basic": [".SBL", ".sbl"],
        "Solidity": [".sol"],
        "SparForte": [".sp"],
        "Specman e": [".e"],
        "SQL": [".cql", ".mysql", ".psql", ".SQL", ".sql", ".tab", ".udf", ".vi"],
        "SQL Data": [".data.sql"],
        "SQL Stored Procedure": [".spc.sql", ".spoc.sql", ".sproc.sql", ".udf.sq"],
        "Squirrel": [".nut"],
        "Standard ML": [".fun", ".sig", ".sml"],
        "Starlark": [".bazel", ".bzl"],
        "Stata": [".ado", ".DO", ".do", ".doh", ".ihlp", ".mata", ".matah", ".sthl"],
        "Stylus": [".styl"],
        "SugarSS": [".sss"],
        "Svelte": [".svelte"],
        "SVG": [".SVG", ".svg"],
        "Swift": [".swift"],
        "SWIG": [".i"],
        "TableGen": [".td"],
        "Tcl/Tk": [".itk", ".tcl", ".tk"],
        "TEAL": [".teal"],
        "Teamcenter met": [".met"],
        "Teamcenter mth": [".mth"],
        "TeX": [
            ".aux",
            ".bbx",
            ".bib",
            ".bst",
            ".cbx",
            ".dtx",
            ".ins",
            ".lbx",
            ".ltx",
            ".mkii",
            ".mkiv",
            ".mkvi",
            ".sty",
            ".tex",
            ".cl",
        ],
        "Text": [".text", ".txt"],
        "Thrift": [".thrift"],
        "TITAN Project File Informataion": [".tpd"],
        "Titanium Style Sheet": [".tss"],
        "TNSDL": [
            ".cii",
            ".cin",
            ".in1",
            ".in2",
            ".in3",
            ".in4",
            ".inf",
            ".interface",
            ".rou",
            ".sdl",
            ".sdt",
            ".spd",
            ".ssc",
            ".ss",
        ],
        "TOML": [".toml"],
        "tspeg": [".jspeg", ".tspeg"],
        "TTCN": [".ttcn", ".ttcn2", ".ttcn3", ".ttcnpp"],
        "Twig": [".twig"],
        "TypeScript": [".tsx", ".ts"],
        "Typst": [".typ"],
        "Umka": [".um"],
        "Unity-Prefab": [".mat", ".prefab"],
        "Vala": [".vala"],
        "Vala Header": [".vapi"],
        "VB for Applications": [".VBA", ".vba"],
        "Velocity Template Language": [".vm"],
        "Verilog-SystemVerilog": [".sv", ".svh", ".v"],
        "VHDL": [
            ".VHD",
            ".vhd",
            ".VHDL",
            ".vhdl",
            ".vhf",
            ".vhi",
            ".vho",
            ".vhs",
            ".vht",
            ".vh",
        ],
        "vim script": [".vim"],
        "Visual Basic": [
            ".BAS",
            ".bas",
            ".ctl",
            ".dsr",
            ".frm",
            ".FRX",
            ".frx",
            ".VBHTML",
            ".vbhtml",
            ".vbp",
            ".vbw",
            ".cl",
        ],
        "Visual Basic .NET": [".VB", ".vb", ".vbproj"],
        "Visual Basic Script": [".VBS", ".vbs"],
        "Visual Fox Pro": [".SCA", ".sca"],
        "Visual Studio Solution": [".sln"],
        "Visualforce Component": [".component"],
        "Visualforce Page": [".page"],
        "Vuejs Component": [".vue"],
        "Web Services Description": [".wsdl"],
        "WebAssembly": [".wast", ".wat"],
        "WGSL": [".wgsl"],
        "Windows Message File": [".mc"],
        "Windows Module Definition": [".def"],
        "Windows Resource File": [".rc", ".rc2"],
        "WiX include": [".wxi"],
        "WiX source": [".wxs"],
        "WiX string localization": [".wxl"],
        "WXML": [".wxml"],
        "WXSS": [".wxss"],
        "X++": [".xpo"],
        "XAML": [".xaml"],
        "xBase": [".prg", ".prw"],
        "xBase Header": [".ch"],
        "XHTML": [".xhtml"],
        "XMI": [".XMI", ".xmi"],
        "XML": [
            ".adml",
            ".admx",
            ".ant",
            ".app.config",
            ".axml",
            ".builds",
            ".ccproj",
            ".ccxml",
            ".classpath",
            ".clixml",
            ".cproject",
            ".cscfg",
            ".csdef",
            ".csl",
            ".ct",
            ".depproj",
            ".ditamap",
            ".ditaval",
            ".dll.config",
            ".dotsettings",
            ".filters",
            ".fsproj",
            ".gmx",
            ".grxml",
            ".iml",
            ".ivy",
            ".jelly",
            ".jsproj",
            ".kml",
            ".launch",
            ".mdpolicy",
            ".mjml",
            ".natvis",
            ".ndproj",
            ".nproj",
            ".nuget.config",
            ".nuspec",
            ".odd",
            ".osm",
            ".packages.config",
            ".pkgproj",
            ".plist",
            ".proj",
            ".project",
            ".props",
            ".ps1xml",
            ".psc1",
            ".pt",
            ".rdf",
            ".resx",
            ".rss",
            ".scxml",
            ".settings.stylecop",
            ".sfproj",
            ".shproj",
            ".srdf",
            ".storyboard",
            ".sttheme",
            ".sublime-snippet",
            ".targets",
            ".tmcommand",
            ".tml",
            ".tmlanguage",
            ".tmpreferences",
            ".tmsnippet",
            ".tmtheme",
            ".urdf",
            ".ux",
            ".vcxproj",
            ".vsixmanifest",
            ".vssettings",
            ".vstemplate",
            ".vxml",
            ".web.config",
            ".web.debug.config",
            ".web.release.config",
            ".wsf",
            ".x3d",
            ".xacro",
            ".xib",
            ".xlf",
            ".xliff",
            ".XML",
            ".xml",
            ".xml.dist",
            ".xproj",
            ".xspec",
            ".xul",
            ".zcm",
        ],
        "XQuery": [".xq", ".xql", ".xqm", ".xquery", ".xqy"],
        "XSD": [".XSD", ".xsd"],
        "XSLT": [".XSL", ".xsl", ".XSLT", ".xslt"],
        "Xtend": [".xtend"],
        "yacc": [".y", ".yacc"],
        "YAML": [
            ".clang-format",
            ".clang-tidy",
            ".gemrc",
            ".glide.lock",
            ".mir",
            ".reek",
            ".rviz",
            ".sublime-syntax",
            ".syntax",
            ".yaml",
            ".yaml-tmlanguage",
            ".yml",
            ".yml.mysq",
        ],
        "Zig": [".zig"],
        "zsh": [".zsh"],
    }
    """ dict: A dictionary of languages and their extensions. """

    extension_to_language: dict[str, str] = {}
    """ dict: A dictionary of extensions and their languages. """

    for language, extstensions in language_to_extensions.items():
        for extension in extstensions:
            extension_to_language[extension] = language

    @classmethod
    def get_extensions(cls, language: str) -> list[str]:
        """
        get_extensions Get the extensions for a given language.

        Args:
            language (str): The language for which to get the extensions.

        Returns:
            list[str]: A list of extensions for the given language.
        """
        return cls.language_to_extensions.get(language, [])

    @classmethod
    def get_language(cls, extension: str) -> str:
        """
        get_language Get the language for a given extension.

        Args:
            extension (str): The extension for which to get the language.

        Returns:
            str: The language for the given extension.
        """
        return cls.extension_to_language.get(extension, "")
