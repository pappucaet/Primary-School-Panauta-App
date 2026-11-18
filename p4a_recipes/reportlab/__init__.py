from pythonforandroid.recipe import PyProjectRecipe

class ReportLabRecipe(PyProjectRecipe):
    version = '4.2.5'
    url = 'https://pythonhosted.org{version}.tar.gz'
    depends = ['setuptools', 'pillow']

recipe = ReportLabRecipe()
