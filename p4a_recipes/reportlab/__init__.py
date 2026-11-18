from pythonforandroid.recipe import PythonRecipe

class ReportLabRecipe(PythonRecipe):
    version = '4.2.5'
    host = 'files.pythonhosted.org'
    url = 'https://' + host + '/packages/source/r/reportlab/reportlab-{version}.tar.gz'
    depends = ['setuptools', 'pillow']
    call_hostpython_via_targetpython = False

recipe = ReportLabRecipe()
