from pythonforandroid.recipe import PyProjectRecipe

class ReportLabRecipe(PyProjectRecipe):
    version = '4.2.5'
    host = 'files.pythonhosted.org'
    url = 'https://' + host + '/packages/source/r/reportlab/reportlab-{version}.tar.gz'
    depends = ['setuptools', 'pillow']

recipe = ReportLabRecipe()
